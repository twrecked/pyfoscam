# pyfoscam v0.1.0-alpha.4 — More reliable recording downloads

- Check that a camera recording has the same nonzero size on two FTP checks 10 seconds apart before downloading it. Verify the transferred byte count and check again that the source size did not change during the transfer.
- Validate that converted MP4s contain video before caching them. Header-only copies from earlier versions can be retried if the original is still on the camera.
- Create and clean up temporary recording directories off the event loop, including cleanup after cancellation. This addresses Home Assistant's blocking `scandir()` warning during downloads.

MP4 conversion uses `ffmpeg` and requires `ffprobe` to validate the output.
