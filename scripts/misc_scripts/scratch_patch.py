with open('store/models.py', 'a') as f:
    f.write('''\n
class AgentWeightageRow(Base):
    __tablename__ = "agent_weightages"

    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), primary_key=True)
    weight_p: Mapped[float] = mapped_column(Float)
    weight_q: Mapped[float] = mapped_column(Float)
    weight_e: Mapped[float] = mapped_column(Float)
    weight_v: Mapped[float] = mapped_column(Float)
    weight_r: Mapped[float] = mapped_column(Float)
    weight_g: Mapped[float] = mapped_column(Float)
    weight_c: Mapped[float] = mapped_column(Float)
    total_weight: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
''')
