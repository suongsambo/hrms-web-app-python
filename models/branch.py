# models/branch.py
from datetime import datetime
from app import db


class Branch(db.Model):
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255))
    branch_name = db.Column(db.String(100), nullable=False)
    branch_manager_name = db.Column(db.String(100))
    contact_number = db.Column(db.String(20))
    address = db.Column(db.String(255))
    register_date = db.Column(db.DateTime, default=datetime.utcnow)
    local_description = db.Column(db.String(255))
    local_address = db.Column(db.String(255))
    local_branch_manager_name = db.Column(db.String(100))
    status = db.Column(db.String(50), default="Active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Branch {self.branch_name}>"

    @staticmethod
    def get_all_branches():
        return Branch.query.all()

    @staticmethod
    def get_branch_by_id(branch_id):
        return Branch.query.get(branch_id)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()
