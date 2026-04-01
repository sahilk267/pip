"""Auto-generated Alembic migration"""

revision = "${up_revision}"
down_revision = "${down_revision}"
branch_labels = ${branch_labels if branch_labels else None}
depends_on = ${depends_on if depends_on else None}

from alembic import op
import sqlalchemy as sa


${imports if imports else ""}


${upgrade if upgrade else "def upgrade():\n    pass\n"}

${downgrade if downgrade else "def downgrade():\n    pass\n"}
