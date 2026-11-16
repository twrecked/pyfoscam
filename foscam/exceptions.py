"""Exceptions for pyfoscam."""


class FoscamError(Exception):
    """Base exception for pyfoscam."""


class FoscamAuthError(FoscamError):
    """Authentication failed."""


class FoscamConnectionError(FoscamError):
    """Failed to connect to Foscam device or FTP service."""


class FoscamCommandError(FoscamError):
    """Command execution failed on camera."""


class FoscamMediaError(FoscamError):
    """Media download or transcoding failure."""


class FoscamConfigError(FoscamError):
    """Configuration error."""
