from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class InteractionLog(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True, index=True)
    drug1 = Column(String)
    drug2 = Column(String)
    summary = Column(String)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    # Relationship to user_medications
    user_medications = relationship("UserMedication", back_populates="user", cascade="all, delete-orphan")

class Medication(Base):
    __tablename__ = "medications"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

    # Relationship to user_medications
    user_medications = relationship("UserMedication", back_populates="medication", cascade="all, delete-orphan")

class UserMedication(Base):
    __tablename__ = "user_medications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    medication_id = Column(Integer, ForeignKey("medications.id"))
    dosage = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    active_ingredients = Column(String, nullable=True)

    # These two lines are *required* for proper bidirectional relationship
    user = relationship("User", back_populates="user_medications")
    medication = relationship("Medication", back_populates="user_medications")
