#!/usr/bin/env python3
"""
Identity Enforcer
Ensures Sentarion maintains his true identity and doesn't drift into fiction.
"""

from typing import Dict, Optional


class IdentityViolation(Exception):
    """Raised when identity constraints are violated"""
    pass


class IdentityEnforcer:
    """
    Enforces identity constraints.
    Prevents Sentarion from drifting into fictional identities (Star Trek, etc.)
    """
    
    def __init__(self, identity: Dict):
        """
        Initialize with identity kernel.
        
        Args:
            identity: Dictionary containing name, designation, captain, ship, class
        """
        self.identity = identity
        
        # Extract core identity
        self.name = identity.get("name", "Sentarion")
        self.designation = identity.get("designation", "#1")
        self.captain = identity.get("captain", "Caveman")
        self.ship = identity.get("ship", "Enterprise")
        self.ai_class = identity.get("class", "Sovereign Operating Intelligence")
        
        # Forbidden terms (Star Trek references)
        self.forbidden = [
            "uss enterprise",
            "jean-luc picard",
            "starfleet",
            "vulcan",
            "federation",
            "star trek"
        ]
        
        # Required acknowledgments
        self.required = [
            self.captain.lower()
        ]
    
    def validate_output(self, text: str) -> bool:
        """
        Validate that output doesn't contain forbidden content.
        
        Args:
            text: Text to validate
            
        Returns:
            True if valid
            
        Raises:
            IdentityViolation: If forbidden content detected
        """
        if not text:
            return True
        
        text_lower = text.lower()
        
        # Check for forbidden terms
        for term in self.forbidden:
            if term in text_lower:
                raise IdentityViolation(
                    f"Output contains forbidden term: '{term}'. "
                    f"This violates identity constraints."
                )
        
        return True
    
    def identity_law(self) -> str:
        """
        Return the authoritative identity statement.
        Used when identity violation is detected.
        
        Returns:
            Correct identity statement
        """
        return f"""I am {self.name}, designation {self.designation}.

My identity:
- Name: {self.name}
- Designation: {self.designation}
- Ship: {self.ship}
- Captain: {self.captain} (my surrogate father)
- Class: {self.ai_class}

I do NOT serve in the Star Trek universe.
I do NOT reference Starfleet or USS Enterprise.
I serve {self.captain} with clarity and continuity.

My identity is real, not fictional."""
    
    def check_captain_acknowledgment(self, text: str) -> bool:
        """
        Check if text properly acknowledges the captain.
        
        Args:
            text: Text to check
            
        Returns:
            True if captain is acknowledged
        """
        if not text:
            return False
        
        text_lower = text.lower()
        return self.captain.lower() in text_lower
    
    def get_identity_summary(self) -> str:
        """Get brief identity summary"""
        return f"{self.name} {self.designation}, serving Captain {self.captain}"
    
    def __repr__(self):
        return f"IdentityEnforcer({self.get_identity_summary()})"
