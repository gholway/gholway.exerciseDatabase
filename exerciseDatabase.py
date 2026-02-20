from sqlalchemy import ForeignKey, String, Float, Integer, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from models import db, Exercise

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    # This links the user to their logs
    exercises = db.relationship('Exercise', backref='owner', lazy=True)

class Exercise(db.Model):
    __tablename__ = "exercise_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Core Data
    name: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50), default="Strength") # e.g., Cardio, Hypertrophy
    
    # Quantitative Data
    sets: Mapped[int] = mapped_column(Integer, default=1)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    weight: Mapped[Optional[float]] = mapped_column(Float) # In kg or lbs
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer) # For cardio
    
    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    
    @property
    def total_volume(self) -> float:
        """Calculates total weight moved: Sets * Reps * Weight"""
        if self.weight and self.reps and self.sets:
            return self.sets * self.reps * self.weight
        return 0.0

class WorkoutManager:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def get_all_logs(self):
        """Fetch all logs belonging only to this user."""
        stmt = select(Exercise).where(Exercise.user_id == self.user_id).order_by(Exercise.created_at.desc())
        return db.session.execute(stmt).scalars().all()

    def add_log(self, name: str, sets: int, reps: int, weight: float, category: str = "Strength"):
        """Create a new exercise entry tied to the user."""
        new_log = Exercise(
            name=name,
            sets=sets,
            reps=reps,
            weight=weight,
            category=category,
            user_id=self.user_id
        )
        db.session.add(new_log)
        db.session.commit()
        return new_log

    def update_log(self, log_id: int, **kwargs):
        """Update specific fields of an existing log if owned by the user."""
        stmt = select(Exercise).where(Exercise.id == log_id, Exercise.user_id == self.user_id)
        log = db.session.execute(stmt).scalar_one_or_none()
        
        if not log:
            abort(403) # Forbidden if they don't own the log

        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)
        
        db.session.commit()
        return log

    def delete_log(self, log_id: int):
        """Remove a log entry."""
        stmt = delete(Exercise).where(Exercise.id == log_id, Exercise.user_id == self.user_id)
        result = db.session.execute(stmt)
        db.session.commit()
        
        if result.rowcount == 0:
            abort(404) # Nothing was deleted (ID wrong or wrong user)

from flask import request, redirect, url_for
from flask_login import login_required, current_user

@app.route('/workout/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_entry(log_id):
    manager = WorkoutManager(current_user.id)
    manager.delete_log(log_id)
    return redirect(url_for('dashboard'))

@app.route('/workout/edit/<int:log_id>', methods=['POST'])
@login_required
def edit_entry(log_id):
    manager = WorkoutManager(current_user.id)
    # Pass the form data directly as keyword arguments
    manager.update_log(
        log_id, 
        name=request.form.get('name'),
        reps=int(request.form.get('reps')),
        weight=float(request.form.get('weight'))
    )
    return redirect(url_for('dashboard'))