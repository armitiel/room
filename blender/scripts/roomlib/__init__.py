"""Wspolny rdzen projektu Room.

Modul celowo nie importuje bpy: te same funkcje musza dzialac
w zwyklym Pythonie (CI, backend) i w Pythonie wbudowanym w Blendera.
"""

__all__ = ["geometry", "scene_io", "validate", "constants"]
