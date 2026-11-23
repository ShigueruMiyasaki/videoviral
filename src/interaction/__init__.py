"""Níveis de interação e plano de falas do avatar."""

from src.interaction.levels import LEVELS, level_catalog
from src.interaction.planner import ScriptPlan, build_plan

__all__ = ["LEVELS", "ScriptPlan", "build_plan", "level_catalog"]
