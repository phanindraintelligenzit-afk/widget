# -*- coding: utf-8 -*-
from pathlib import Path

models_path = Path('store/models.py')
content = models_path.read_text(encoding='utf-8')

old_agent = '''class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(64), default="ACTIVE")
    baseline_human_output: Mapped[float] = mapped_column(Float, default=100.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)'''

new_agent = '''class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(64), default="ACTIVE")
    baseline_human_output: Mapped[float] = mapped_column(Float, default=100.0)
    owner_id: Mapped[str] = mapped_column(String(256), nullable=True)  # RBAC ownership
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)'''

if 'owner_id' not in content:
    content = content.replace(old_agent, new_agent)
    models_path.write_text(content, encoding='utf-8')
    print("Added owner_id to AgentRow")
else:
    print("owner_id already exists")
