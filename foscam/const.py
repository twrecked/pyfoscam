"""Constants for pyfoscam."""

DEFAULT_PORT = 88
DEFAULT_RTSP_PORT = 554
DEFAULT_FTP_PORT = 50021
DEFAULT_TIMEOUT = 10

PTZ_UP = "up"
PTZ_DOWN = "down"
PTZ_LEFT = "left"
PTZ_RIGHT = "right"
PTZ_TOP_LEFT = "top_left"
PTZ_TOP_RIGHT = "top_right"
PTZ_BOTTOM_LEFT = "bottom_left"
PTZ_BOTTOM_RIGHT = "bottom_right"

PTZ_COMMANDS = {
    PTZ_UP: "ptzMoveUp",
    PTZ_DOWN: "ptzMoveDown",
    PTZ_LEFT: "ptzMoveLeft",
    PTZ_RIGHT: "ptzMoveRight",
    PTZ_TOP_LEFT: "ptzMoveTopLeft",
    PTZ_TOP_RIGHT: "ptzMoveTopRight",
    PTZ_BOTTOM_LEFT: "ptzMoveBottomLeft",
    PTZ_BOTTOM_RIGHT: "ptzMoveBottomRight",
}

DEFAULT_PTZ_TRAVEL_TIME = 0.125

ZOOM_IN = "in"
ZOOM_OUT = "out"

ZOOM_COMMANDS = {
    ZOOM_IN: "zoomIn",
    ZOOM_OUT: "zoomOut",
}

DEFAULT_ZOOM_TRAVEL_TIME = 0.125

FOCUS_NEAR = "near"
FOCUS_FAR = "far"

FOCUS_COMMANDS = {
    FOCUS_NEAR: "focusNear",
    FOCUS_FAR: "focusFar",
}

DEFAULT_FOCUS_TRAVEL_TIME = 0.125
