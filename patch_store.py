import sys
from pathlib import Path

file_path = Path('store/models.py')
content = file_path.read_text()

if 'class ExecutionRow(Base)' not in content:
    new_model = '''

class ExecutionRow(Base):
    __tablename__ = "executions"
    id = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    status = Column(String)  # pending, running, completed, failed
    start_time = Column(Float)
    end_time = Column(Float, nullable=True)
    exit_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)
'''
    
    content += new_model
    file_path.write_text(content)
    print("Added ExecutionRow")
else:
    print("ExecutionRow already exists")
