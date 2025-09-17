from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Organization, BusinessContext, Agent
from app.schemas import (
    OrganizationCreate,
    BusinessContextCreate,
    BusinessContextUpdate,
    IntegrationsConfig,
    DocumentUploadResponse,
    OnboardingStepResponse,
    TrainingStatus,
    OnboardingStatus
)
from app.utils import (
    get_current_user,
    require_organization_admin,
    raise_bad_request,
    raise_not_found,
    raise_conflict,
    AgentTrainingException,
    DocumentProcessingException,
    OnboardingException
)
from app.core import document_processor, agent_trainer
import slugify

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/start", response_model=OnboardingStepResponse)
async def start_onboarding(
    org_data: OrganizationCreate,
    business_context_data: BusinessContextCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 1: Create organization and initial business context
    """
    try:
        # Check if user already has an organization
        if current_user.organization_id:
            raise_conflict("User already belongs to an organization")

        # Create organization slug
        org_slug = slugify.slugify(org_data.name)

        # Check if slug already exists
        result = await db.execute(select(Organization).where(Organization.slug == org_slug))
        if result.scalar_one_or_none():
            # Add timestamp to make it unique
            import time
            org_slug = f"{org_slug}-{int(time.time())}"

        # Create organization
        organization = Organization(
            name=org_data.name,
            slug=org_slug,
            description=org_data.description,
            industry=org_data.industry,
            size_range=org_data.size_range,
            website=org_data.website,
            country=org_data.country,
            timezone=org_data.timezone,
            onboarding_step="business_context"
        )

        db.add(organization)
        await db.flush()  # Get the ID without committing

        # Create business context
        business_context = BusinessContext(
            organization_id=organization.id,
            business_name=business_context_data.business_name,
            industry=business_context_data.industry,
            business_description=business_context_data.business_description,
            target_audience=business_context_data.target_audience,
            brand_tone=business_context_data.brand_tone,
            brand_voice=business_context_data.brand_voice,
            brand_guidelines=business_context_data.brand_guidelines,
            brand_values=business_context_data.brand_values,
            products=business_context_data.products,
            services=business_context_data.services,
            value_proposition=business_context_data.value_proposition,
            customer_personas=business_context_data.customer_personas,
            pain_points=business_context_data.pain_points,
            preferred_language=business_context_data.preferred_language,
            communication_style=business_context_data.communication_style,
            response_length=business_context_data.response_length,
            faq_data=business_context_data.faq_data,
            policies=business_context_data.policies,
            contact_info=business_context_data.contact_info,
            business_hours=business_context_data.business_hours,
            sample_conversations=business_context_data.sample_conversations,
            do_not_answer=business_context_data.do_not_answer,
            escalation_triggers=business_context_data.escalation_triggers
        )

        db.add(business_context)

        # Update user to be organization owner
        current_user.organization_id = organization.id
        current_user.role = "owner"
        current_user.is_onboarded = True

        await db.commit()

        return OnboardingStepResponse(
            step="business_context",
            completed=True,
            message="Organization and business context created successfully",
            next_step="documents",
            data={
                "organization_id": str(organization.id),
                "business_context_id": str(business_context.id)
            }
        )

    except Exception as e:
        await db.rollback()
        raise OnboardingException(f"Failed to start onboarding: {str(e)}")


@router.post("/upload-documents", response_model=OnboardingStepResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_organization_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 2: Process and index business documents
    """
    try:
        if not current_user.organization_id:
            raise_bad_request("No organization found for user")

        # Get organization and business context
        org_result = await db.execute(
            select(Organization, BusinessContext)
            .join(BusinessContext)
            .where(Organization.id == current_user.organization_id)
        )
        org_data = org_result.first()

        if not org_data:
            raise_not_found("Organization or business context not found")

        organization, business_context = org_data

        # Validate files
        validation_results = await document_processor.validate_files(files)
        invalid_files = [r for r in validation_results if not r["valid"]]

        if invalid_files:
            raise_bad_request(
                "Invalid files found",
                details={"invalid_files": invalid_files}
            )

        # Process documents
        processing_results = await document_processor.process_documents(
            files=files,
            organization_id=str(organization.id),
            business_context_id=str(business_context.id)
        )

        # Update business context with document metadata
        business_context.documents_metadata = processing_results["processing_details"]
        business_context.total_documents = processing_results["processed_files"]
        business_context.total_chunks = processing_results["total_chunks"]
        business_context.vector_store_id = processing_results["collection_name"]

        # Update organization onboarding step
        organization.onboarding_step = "integrations"

        await db.commit()

        return OnboardingStepResponse(
            step="documents",
            completed=True,
            message=f"Successfully processed {processing_results['processed_files']} documents",
            next_step="integrations",
            data={
                "processed_files": processing_results["processed_files"],
                "total_chunks": processing_results["total_chunks"],
                "failed_files": processing_results["failed_files"]
            }
        )

    except DocumentProcessingException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document processing failed: {str(e)}"
        )
    except Exception as e:
        raise OnboardingException(f"Failed to upload documents: {str(e)}")


@router.post("/configure-integrations", response_model=OnboardingStepResponse)
async def configure_integrations(
    integrations: IntegrationsConfig,
    current_user: User = Depends(require_organization_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 3: Configure third-party integrations
    """
    try:
        if not current_user.organization_id:
            raise_bad_request("No organization found for user")

        # Get business context
        result = await db.execute(
            select(BusinessContext, Organization)
            .join(Organization)
            .where(Organization.id == current_user.organization_id)
        )
        context_data = result.first()

        if not context_data:
            raise_not_found("Business context not found")

        business_context, organization = context_data

        # Update integrations configuration
        integrations_dict = integrations.dict(exclude_none=True)
        business_context.integrations_config = integrations_dict

        # Update organization onboarding step
        organization.onboarding_step = "training"

        await db.commit()

        return OnboardingStepResponse(
            step="integrations",
            completed=True,
            message="Integrations configured successfully",
            next_step="training",
            data={
                "configured_integrations": list(integrations_dict.keys())
            }
        )

    except Exception as e:
        raise OnboardingException(f"Failed to configure integrations: {str(e)}")


@router.post("/train-agent", response_model=OnboardingStepResponse)
async def train_principal_agent(
    current_user: User = Depends(require_organization_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 4: Train the Principal Agent with business context
    """
    try:
        if not current_user.organization_id:
            raise_bad_request("No organization found for user")

        # Get business context
        result = await db.execute(
            select(BusinessContext, Organization)
            .join(Organization)
            .where(Organization.id == current_user.organization_id)
        )
        context_data = result.first()

        if not context_data:
            raise_not_found("Business context not found")

        business_context, organization = context_data

        # Check if business context is complete
        if not business_context.is_complete:
            raise_bad_request("Business context is incomplete. Please complete all required fields.")

        # Check if agent already exists
        agent_result = await db.execute(
            select(Agent)
            .where(
                Agent.organization_id == current_user.organization_id,
                Agent.type == "principal",
                Agent.is_active_version == True
            )
        )
        existing_agent = agent_result.scalar_one_or_none()

        if existing_agent:
            raise_conflict("Principal agent already exists for this organization")

        # Train the agent
        agent = await agent_trainer.train_principal_agent(
            db=db,
            organization_id=str(current_user.organization_id),
            business_context=business_context
        )

        # Update organization onboarding
        organization.onboarding_step = "completed"
        organization.onboarding_completed = True

        await db.commit()

        return OnboardingStepResponse(
            step="training",
            completed=True,
            message="Principal agent trained successfully",
            next_step=None,
            data={
                "agent_id": str(agent.id),
                "agent_status": agent.status,
                "validation_score": agent.validation_score,
                "training_completed": agent.training_completed
            }
        )

    except AgentTrainingException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Agent training failed: {str(e)}"
        )
    except Exception as e:
        raise OnboardingException(f"Failed to train agent: {str(e)}")


@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current onboarding status
    """
    try:
        if not current_user.organization_id:
            raise_not_found("No organization found for user")

        # Get organization and business context
        result = await db.execute(
            select(Organization, BusinessContext)
            .outerjoin(BusinessContext)
            .where(Organization.id == current_user.organization_id)
        )
        org_data = result.first()

        if not org_data:
            raise_not_found("Organization not found")

        organization, business_context = org_data

        # Get agent status
        agent_result = await db.execute(
            select(Agent)
            .where(
                Agent.organization_id == current_user.organization_id,
                Agent.type == "principal",
                Agent.is_active_version == True
            )
        )
        agent = agent_result.scalar_one_or_none()

        # Define step progression
        steps = ["created", "business_context", "documents", "integrations", "training", "completed"]
        current_step_index = steps.index(organization.onboarding_step) if organization.onboarding_step in steps else 0
        completed_steps = steps[:current_step_index]

        # Calculate progress
        progress_percentage = (current_step_index / (len(steps) - 1)) * 100

        # Determine next action
        next_action = None
        if organization.onboarding_step == "business_context" and business_context and not business_context.is_complete:
            next_action = "Complete business context information"
        elif organization.onboarding_step == "documents" and (not business_context or business_context.total_documents == 0):
            next_action = "Upload business documents"
        elif organization.onboarding_step == "integrations":
            next_action = "Configure integrations (optional)"
        elif organization.onboarding_step == "training" and not agent:
            next_action = "Train your principal agent"

        return OnboardingStatus(
            organization_id=organization.id,
            current_step=organization.onboarding_step,
            completed_steps=completed_steps,
            progress_percentage=progress_percentage,
            can_proceed=organization.onboarding_step != "completed",
            next_action=next_action,
            business_context_complete=business_context.is_complete if business_context else False,
            documents_uploaded=business_context.total_documents if business_context else 0,
            integrations_configured=len(business_context.integrations_config) if business_context and business_context.integrations_config else 0,
            agent_trained=agent is not None and agent.training_completed
        )

    except Exception as e:
        raise OnboardingException(f"Failed to get onboarding status: {str(e)}")


@router.put("/business-context", response_model=OnboardingStepResponse)
async def update_business_context(
    context_update: BusinessContextUpdate,
    current_user: User = Depends(require_organization_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update business context during onboarding
    """
    try:
        if not current_user.organization_id:
            raise_bad_request("No organization found for user")

        # Get business context
        result = await db.execute(
            select(BusinessContext)
            .where(BusinessContext.organization_id == current_user.organization_id)
        )
        business_context = result.scalar_one_or_none()

        if not business_context:
            raise_not_found("Business context not found")

        # Update fields
        update_data = context_update.dict(exclude_none=True)
        for field, value in update_data.items():
            setattr(business_context, field, value)

        await db.commit()

        return OnboardingStepResponse(
            step="business_context_update",
            completed=True,
            message="Business context updated successfully",
            data={
                "is_complete": business_context.is_complete,
                "updated_fields": list(update_data.keys())
            }
        )

    except Exception as e:
        raise OnboardingException(f"Failed to update business context: {str(e)}")


@router.get("/training-status/{agent_id}", response_model=TrainingStatus)
async def get_training_status(
    agent_id: UUID,
    current_user: User = Depends(require_organization_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get agent training status
    """
    try:
        # Get agent
        result = await db.execute(
            select(Agent)
            .where(
                Agent.id == agent_id,
                Agent.organization_id == current_user.organization_id
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise_not_found("Agent not found")

        # Calculate progress based on status
        progress_map = {
            "created": 0.0,
            "training": 0.5,
            "ready": 1.0,
            "error": 0.0
        }

        return TrainingStatus(
            agent_id=agent.id,
            status=agent.status,
            progress=progress_map.get(agent.status, 0.0),
            estimated_completion=agent.training_completed_at,
            validation_score=agent.validation_score,
            error_message=agent.validation_details.get("error") if agent.validation_details else None
        )

    except Exception as e:
        raise OnboardingException(f"Failed to get training status: {str(e)}")