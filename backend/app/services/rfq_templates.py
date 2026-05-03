"""RFQ template management for bulk sourcing."""
from typing import Any
from sqlalchemy.orm import Session
from ..models_extended import RFQTemplate, RFQTemplateItem


def create_rfq_template(
    db: Session,
    name: str,
    category: str,
    description: str = "",
    created_by: str = "system",
    is_public: bool = False,
) -> dict[str, Any]:
    """Create a new RFQ template."""
    template = RFQTemplate(
        name=name,
        description=description,
        category=category,
        created_by=created_by,
        is_public=is_public,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "template_id": template.id,
        "name": template.name,
        "category": template.category,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def add_template_item(
    db: Session,
    template_id: int,
    product_name: str,
    quantity: float,
    target_price: float | None = None,
    lead_time_days: int | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Add product to RFQ template."""
    template = db.query(RFQTemplate).filter(RFQTemplate.id == template_id).first()
    if not template:
        raise ValueError(f"Template {template_id} not found")

    item = RFQTemplateItem(
        template_id=template_id,
        product_name=product_name,
        quantity=quantity,
        target_price=target_price,
        lead_time_days=lead_time_days,
        notes=notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "item_id": item.id,
        "template_id": template_id,
        "product": product_name,
        "quantity": quantity,
    }


def get_template(db: Session, template_id: int) -> dict[str, Any]:
    """Get template with all items."""
    template = db.query(RFQTemplate).filter(RFQTemplate.id == template_id).first()
    if not template:
        raise ValueError(f"Template {template_id} not found")

    items = db.query(RFQTemplateItem).filter(RFQTemplateItem.template_id == template_id).all()

    return {
        "template_id": template.id,
        "name": template.name,
        "category": template.category,
        "description": template.description,
        "items": [
            {
                "product": item.product_name,
                "quantity": item.quantity,
                "target_price": item.target_price,
                "lead_time_days": item.lead_time_days,
            }
            for item in items
        ],
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def list_templates(
    db: Session,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List RFQ templates."""
    query = db.query(RFQTemplate)
    if category:
        query = query.filter(RFQTemplate.category == category)

    templates = query.order_by(RFQTemplate.use_count.desc(), RFQTemplate.created_at.desc()).limit(limit).all()

    return [
        {
            "template_id": t.id,
            "name": t.name,
            "category": t.category,
            "use_count": t.use_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in templates
    ]


def use_template(
    db: Session,
    template_id: int,
    new_rfq_id: int,
) -> dict[str, Any]:
    """Record template usage."""
    template = db.query(RFQTemplate).filter(RFQTemplate.id == template_id).first()
    if not template:
        raise ValueError(f"Template {template_id} not found")

    template.use_count += 1
    db.add(template)
    db.commit()

    return {
        "template_id": template_id,
        "use_count": template.use_count,
        "new_rfq_id": new_rfq_id,
    }
