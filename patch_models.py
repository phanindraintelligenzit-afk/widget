# -*- coding: utf-8 -*-
import re
from pathlib import Path

models_path = Path('store/models.py')
content = models_path.read_text(encoding='utf-8')

old_exec = '''class ExecutionRow(Base):
    __tablename__ = "executions"
    id = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    status = Column(String)  # pending, running, completed, failed
    start_time = Column(Float)
    end_time = Column(Float, nullable=True)
    exit_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)'''

new_exec = '''from sqlalchemy import Column

class ExecutionRow(Base):
    __tablename__ = "executions"
    id = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    status = Column(String)  # pending, running, completed, failed
    start_time = Column(Float)
    end_time = Column(Float, nullable=True)
    exit_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)'''

content = content.replace(old_exec, new_exec)
models_path.write_text(content, encoding='utf-8')
