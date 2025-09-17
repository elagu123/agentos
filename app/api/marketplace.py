"""
Marketplace API endpoints for template publishing and discovery.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, text
from pydantic import BaseModel, Field, validator

from app.database import get_db
from app.models.marketplace import (
    MarketplaceTemplate, TemplateRating, TemplateInstallation,
    TemplateReport, TemplateCollection, TemplateAnalytics,
    TemplateStatus, TemplateVisibility
)
from app.models.user import User
from app.models.organization import Organization
from app.core.auth import get_current_user
from app.utils.security import validate_template_security
from app.utils.slugify import slugify

router = APIRouter()


# Request/Response Models
class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10, max_length=2000)
    category: str = Field(..., min_length=2, max_length=100)
    tags: List[str] = Field(default_factory=list, max_items=10)
    workflow_definition: Dict[str, Any] = Field(...)
    version: str = Field(default="1.0.0", regex=r"^\d+\.\d+\.\d+$")
    visibility: TemplateVisibility = Field(default=TemplateVisibility.PUBLIC)
    changelog: Optional[str] = Field(None, max_length=1000)
    preview_image_url: Optional[str] = None
    search_keywords: List[str] = Field(default_factory=list, max_items=20)

    @validator('tags', 'search_keywords')
    def validate_tags(cls, v):
        return [tag.strip().lower() for tag in v if tag.strip()]


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    tags: Optional[List[str]] = Field(None, max_items=10)
    workflow_definition: Optional[Dict[str, Any]] = None
    version: Optional[str] = Field(None, regex=r"^\d+\.\d+\.\d+$")
    visibility: Optional[TemplateVisibility] = None
    changelog: Optional[str] = Field(None, max_length=1000)
    preview_image_url: Optional[str] = None


class TemplateSearchRequest(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    is_featured: Optional[bool] = None
    is_certified: Optional[bool] = None
    sort_by: str = Field(default="created_at", regex="^(created_at|rating|downloads|name)$")
    sort_order: str = Field(default="desc", regex="^(asc|desc)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class RatingCreateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review_title: Optional[str] = Field(None, max_length=255)
    review_text: Optional[str] = Field(None, max_length=2000)
    use_case: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    team_size: Optional[str] = Field(None, max_length=50)


class InstallationRequest(BaseModel):
    customization_data: Dict[str, Any] = Field(default_factory=dict)
    installation_type: str = Field(default="standard", regex="^(standard|custom|fork)$")


class ReportCreateRequest(BaseModel):
    reason: str = Field(..., regex="^(spam|inappropriate|broken|copyright|security|other)$")
    description: str = Field(..., min_length=10, max_length=1000)
    evidence_urls: List[str] = Field(default_factory=list, max_items=5)


# Marketplace Template Endpoints
@router.post("/templates", response_model=Dict[str, Any])
async def create_template(
    request: TemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new marketplace template."""
    try:
        # Validate template security
        security_result = await validate_template_security(request.workflow_definition)
        if not security_result.is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"Template security validation failed: {security_result.issues}"
            )

        # Generate unique slug
        base_slug = slugify(request.name)
        slug = base_slug
        counter = 1
        while db.query(MarketplaceTemplate).filter(MarketplaceTemplate.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Create template
        template = MarketplaceTemplate(
            name=request.name,
            description=request.description,
            category=request.category,
            tags=request.tags,
            workflow_definition=request.workflow_definition,
            version=request.version,
            visibility=request.visibility,
            changelog=request.changelog,
            preview_image_url=request.preview_image_url,
            search_keywords=request.search_keywords,
            slug=slug,
            author_id=current_user.id,
            author_name=current_user.full_name,
            organization_id=current_user.organization_id,
            status=TemplateStatus.PENDING_REVIEW if request.visibility == TemplateVisibility.PUBLIC else TemplateStatus.APPROVED
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        return {
            "id": str(template.id),
            "name": template.name,
            "slug": template.slug,
            "status": template.status,
            "message": "Template created successfully"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.get("/templates", response_model=Dict[str, Any])
async def search_templates(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: List[str] = Query([], description="Filter by tags"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating"),
    is_featured: Optional[bool] = Query(None, description="Filter featured templates"),
    is_certified: Optional[bool] = Query(None, description="Filter certified templates"),
    sort_by: str = Query("created_at", regex="^(created_at|rating_average|download_count|name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search and browse marketplace templates."""
    try:
        # Build base query
        query_obj = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.status == TemplateStatus.APPROVED,
            MarketplaceTemplate.visibility == TemplateVisibility.PUBLIC
        )

        # Apply filters
        if query:
            search_filter = or_(
                MarketplaceTemplate.name.ilike(f"%{query}%"),
                MarketplaceTemplate.description.ilike(f"%{query}%"),
                MarketplaceTemplate.search_keywords.op('@>')([query.lower()])
            )
            query_obj = query_obj.filter(search_filter)

        if category:
            query_obj = query_obj.filter(MarketplaceTemplate.category == category)

        if tags:
            for tag in tags:
                query_obj = query_obj.filter(MarketplaceTemplate.tags.op('@>')([tag.lower()]))

        if min_rating is not None:
            query_obj = query_obj.filter(MarketplaceTemplate.rating_average >= min_rating)

        if is_featured is not None:
            query_obj = query_obj.filter(MarketplaceTemplate.is_featured == is_featured)

        if is_certified is not None:
            query_obj = query_obj.filter(MarketplaceTemplate.is_certified == is_certified)

        # Apply sorting
        sort_column = getattr(MarketplaceTemplate, sort_by)
        if sort_order == "desc":
            query_obj = query_obj.order_by(desc(sort_column))
        else:
            query_obj = query_obj.order_by(asc(sort_column))

        # Add secondary sort by created_at for consistency
        if sort_by != "created_at":
            query_obj = query_obj.order_by(desc(MarketplaceTemplate.created_at))

        # Get total count
        total_count = query_obj.count()

        # Apply pagination
        offset = (page - 1) * page_size
        templates = query_obj.offset(offset).limit(page_size).all()

        # Format response
        template_data = []
        for template in templates:
            template_data.append({
                "id": str(template.id),
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "tags": template.tags,
                "author_name": template.author_name,
                "version": template.version,
                "rating_average": template.rating_average,
                "rating_count": template.rating_count,
                "download_count": template.download_count,
                "install_count": template.install_count,
                "is_featured": template.is_featured,
                "is_certified": template.is_certified,
                "preview_image_url": template.preview_image_url,
                "slug": template.slug,
                "created_at": template.created_at.isoformat(),
                "updated_at": template.updated_at.isoformat()
            })

        return {
            "templates": template_data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size
            },
            "filters_applied": {
                "query": query,
                "category": category,
                "tags": tags,
                "min_rating": min_rating,
                "is_featured": is_featured,
                "is_certified": is_certified
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search templates: {str(e)}")


@router.get("/templates/{template_id}", response_model=Dict[str, Any])
async def get_template(
    template_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get detailed template information."""
    try:
        template = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check visibility permissions
        if template.visibility != TemplateVisibility.PUBLIC:
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            if (template.visibility == TemplateVisibility.ORGANIZATION and
                template.organization_id != current_user.organization_id):
                raise HTTPException(status_code=403, detail="Access denied")

            if (template.visibility == TemplateVisibility.PRIVATE and
                template.author_id != current_user.id):
                raise HTTPException(status_code=403, detail="Access denied")

        # Update view count
        template.view_count += 1
        db.commit()

        # Get recent ratings
        recent_ratings = db.query(TemplateRating).filter(
            TemplateRating.template_id == template_id,
            TemplateRating.is_approved == True
        ).order_by(desc(TemplateRating.created_at)).limit(10).all()

        ratings_data = []
        for rating in recent_ratings:
            ratings_data.append({
                "id": str(rating.id),
                "rating": rating.rating,
                "review_title": rating.review_title,
                "review_text": rating.review_text,
                "use_case": rating.use_case,
                "industry": rating.industry,
                "helpful_count": rating.helpful_count,
                "created_at": rating.created_at.isoformat(),
                "user_name": rating.user.full_name if rating.user else "Anonymous"
            })

        return {
            "id": str(template.id),
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "tags": template.tags,
            "workflow_definition": template.workflow_definition,
            "version": template.version,
            "changelog": template.changelog,
            "author_name": template.author_name,
            "rating_average": template.rating_average,
            "rating_count": template.rating_count,
            "download_count": template.download_count,
            "install_count": template.install_count,
            "view_count": template.view_count,
            "is_featured": template.is_featured,
            "is_certified": template.is_certified,
            "preview_image_url": template.preview_image_url,
            "screenshots": template.screenshots,
            "video_url": template.video_url,
            "slug": template.slug,
            "status": template.status,
            "visibility": template.visibility,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat(),
            "published_at": template.published_at.isoformat() if template.published_at else None,
            "recent_ratings": ratings_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get template: {str(e)}")


@router.patch("/templates/{template_id}", response_model=Dict[str, Any])
async def update_template(
    template_id: UUID = Path(...),
    request: TemplateUpdateRequest = ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a marketplace template."""
    try:
        template = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check permissions
        if template.author_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only update your own templates")

        # Update fields
        update_data = request.dict(exclude_unset=True)

        if update_data.get('workflow_definition'):
            # Validate security for workflow updates
            security_result = await validate_template_security(update_data['workflow_definition'])
            if not security_result.is_safe:
                raise HTTPException(
                    status_code=400,
                    detail=f"Template security validation failed: {security_result.issues}"
                )

        for field, value in update_data.items():
            setattr(template, field, value)

        # Update slug if name changed
        if 'name' in update_data:
            base_slug = slugify(update_data['name'])
            slug = base_slug
            counter = 1
            while (db.query(MarketplaceTemplate)
                  .filter(MarketplaceTemplate.slug == slug, MarketplaceTemplate.id != template_id)
                  .first()):
                slug = f"{base_slug}-{counter}"
                counter += 1
            template.slug = slug

        # Reset to pending review if making public changes
        if (template.visibility == TemplateVisibility.PUBLIC and
            template.status == TemplateStatus.APPROVED and
            ('workflow_definition' in update_data or 'name' in update_data or 'description' in update_data)):
            template.status = TemplateStatus.PENDING_REVIEW

        db.commit()
        db.refresh(template)

        return {
            "id": str(template.id),
            "name": template.name,
            "slug": template.slug,
            "status": template.status,
            "message": "Template updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a marketplace template."""
    try:
        template = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check permissions
        if template.author_id != current_user.id and not current_user.is_organization_admin:
            raise HTTPException(status_code=403, detail="You can only delete your own templates")

        db.delete(template)
        db.commit()

        return {"message": "Template deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


# Template Rating Endpoints
@router.post("/templates/{template_id}/ratings", response_model=Dict[str, Any])
async def create_rating(
    template_id: UUID = Path(...),
    request: RatingCreateRequest = ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create or update a rating for a template."""
    try:
        template = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check if user already rated this template
        existing_rating = db.query(TemplateRating).filter(
            TemplateRating.template_id == template_id,
            TemplateRating.user_id == current_user.id
        ).first()

        if existing_rating:
            # Update existing rating
            for field, value in request.dict().items():
                setattr(existing_rating, field, value)
            existing_rating.updated_at = datetime.utcnow()
            rating = existing_rating
        else:
            # Create new rating
            rating = TemplateRating(
                template_id=template_id,
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                **request.dict()
            )
            db.add(rating)

        db.commit()

        # Recalculate template rating average
        avg_rating = db.query(func.avg(TemplateRating.rating)).filter(
            TemplateRating.template_id == template_id,
            TemplateRating.is_approved == True
        ).scalar()

        rating_count = db.query(func.count(TemplateRating.id)).filter(
            TemplateRating.template_id == template_id,
            TemplateRating.is_approved == True
        ).scalar()

        template.rating_average = float(avg_rating) if avg_rating else 0.0
        template.rating_count = rating_count

        db.commit()

        return {
            "id": str(rating.id),
            "rating": rating.rating,
            "template_rating_average": template.rating_average,
            "template_rating_count": template.rating_count,
            "message": "Rating created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create rating: {str(e)}")


# Template Installation Endpoints
@router.post("/templates/{template_id}/install", response_model=Dict[str, Any])
async def install_template(
    template_id: UUID = Path(...),
    request: InstallationRequest = ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Install a template into user's workspace."""
    try:
        template = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check visibility permissions
        if template.visibility == TemplateVisibility.ORGANIZATION:
            if template.organization_id != current_user.organization_id:
                raise HTTPException(status_code=403, detail="Template not accessible")

        if template.visibility == TemplateVisibility.PRIVATE:
            if template.author_id != current_user.id:
                raise HTTPException(status_code=403, detail="Template not accessible")

        # Create installation record
        installation = TemplateInstallation(
            template_id=template_id,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            installation_type=request.installation_type,
            customization_data=request.customization_data
        )

        db.add(installation)

        # Update template stats
        template.install_count += 1
        template.download_count += 1

        db.commit()

        return {
            "installation_id": str(installation.id),
            "template_id": str(template_id),
            "installation_type": request.installation_type,
            "customization_applied": bool(request.customization_data),
            "message": "Template installed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to install template: {str(e)}")


# Template Reporting Endpoints
@router.post("/templates/{template_id}/report", response_model=Dict[str, Any])
async def report_template(
    template_id: UUID = Path(...),
    request: ReportCreateRequest = ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Report a template for review."""
    try:
        template = db.query(MarketplaceTemplate).filter(
            MarketplaceTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Create report
        report = TemplateReport(
            template_id=template_id,
            reporter_id=current_user.id,
            reason=request.reason,
            description=request.description,
            evidence_urls=request.evidence_urls
        )

        db.add(report)
        db.commit()

        return {
            "report_id": str(report.id),
            "template_id": str(template_id),
            "reason": request.reason,
            "message": "Report submitted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to report template: {str(e)}")


# Categories and Statistics
@router.get("/categories", response_model=List[Dict[str, Any]])
async def get_categories(db: Session = Depends(get_db)):
    """Get all template categories with counts."""
    try:
        categories = db.query(
            MarketplaceTemplate.category,
            func.count(MarketplaceTemplate.id).label('count')
        ).filter(
            MarketplaceTemplate.status == TemplateStatus.APPROVED,
            MarketplaceTemplate.visibility == TemplateVisibility.PUBLIC
        ).group_by(MarketplaceTemplate.category).all()

        return [
            {
                "category": category,
                "count": count,
                "slug": slugify(category)
            }
            for category, count in categories
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/stats", response_model=Dict[str, Any])
async def get_marketplace_stats(db: Session = Depends(get_db)):
    """Get marketplace statistics."""
    try:
        total_templates = db.query(func.count(MarketplaceTemplate.id)).filter(
            MarketplaceTemplate.status == TemplateStatus.APPROVED,
            MarketplaceTemplate.visibility == TemplateVisibility.PUBLIC
        ).scalar()

        total_downloads = db.query(func.sum(MarketplaceTemplate.download_count)).filter(
            MarketplaceTemplate.status == TemplateStatus.APPROVED,
            MarketplaceTemplate.visibility == TemplateVisibility.PUBLIC
        ).scalar() or 0

        total_authors = db.query(func.count(func.distinct(MarketplaceTemplate.author_id))).filter(
            MarketplaceTemplate.status == TemplateStatus.APPROVED,
            MarketplaceTemplate.visibility == TemplateVisibility.PUBLIC
        ).scalar()

        avg_rating = db.query(func.avg(MarketplaceTemplate.rating_average)).filter(
            MarketplaceTemplate.status == TemplateStatus.APPROVED,
            MarketplaceTemplate.visibility == TemplateVisibility.PUBLIC,
            MarketplaceTemplate.rating_count > 0
        ).scalar()

        return {
            "total_templates": total_templates,
            "total_downloads": total_downloads,
            "total_authors": total_authors,
            "average_rating": round(float(avg_rating), 2) if avg_rating else 0.0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")