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
    PTZ_UP: "ptz_move_up",
    PTZ_DOWN: "ptz_move_down",
    PTZ_LEFT: "ptz_move_left",
    PTZ_RIGHT: "ptz_move_right",
    PTZ_TOP_LEFT: "ptz_move_top_left",
    PTZ_TOP_RIGHT: "ptz_move_top_right",
    PTZ_BOTTOM_LEFT: "ptz_move_bottom_left",
    PTZ_BOTTOM_RIGHT: "ptz_move_bottom_right",
}

DEFAULT_PTZ_TRAVEL_TIME = 0.125
