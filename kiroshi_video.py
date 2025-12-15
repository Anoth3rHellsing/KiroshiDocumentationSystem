# -*- coding: utf-8 -*-
"""
Video optimization utilities for Kiroshi.
"""
import os
import tempfile
import shutil
import io
import logging
import streamlit as st

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    VideoFileClip = None

def optimize_video(file_buffer: io.BytesIO, filename: str) -> io.BytesIO | None:
    """
    Compress and optimize a video file to 720p height and 15 fps.

    Args:
        file_buffer: The input video content as a BytesIO object.
        filename: The original filename (used for extension detection).

    Returns:
        A BytesIO object containing the optimized video, or None if optimization failed.
    """
    if VideoFileClip is None:
        logging.error("moviepy not installed. Cannot optimize video.")
        return None

    # Determine file extension
    _, ext = os.path.splitext(filename)
    if not ext:
        ext = ".mp4"

    # Create temporary files for input and output
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_in, \
         tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_out:

        temp_in_path = temp_in.name
        temp_out_path = temp_out.name

        try:
            # Write input buffer to temp file
            temp_in.write(file_buffer.getvalue())
            temp_in.flush()
            temp_in.close() # Close handle so moviepy can open it
            temp_out.close() # Close handle so moviepy can write to it

            # Process video
            with VideoFileClip(temp_in_path) as clip:
                # Resize to 720p height (width calculated automatically to keep aspect ratio)
                # If height is already <= 720, keep it as is?
                # User requirement: "720p 15 fps esta bien". Usually implies downscaling.
                target_height = 720

                # Check aspect ratio to avoid upscaling if already small,
                # but user specifically asked for "compression".
                # Resize typically implies changing dimension.

                if clip.h > target_height:
                    new_clip = clip.resize(height=target_height)
                else:
                    new_clip = clip

                # Set fps to 15
                new_clip = new_clip.set_fps(15)

                # Write output
                # moviepy writes to stdout/stderr which might clutter logs, pass verbose=False or logger=None
                # v1.0.3 uses write_videofile
                new_clip.write_videofile(
                    temp_out_path,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=f"{temp_out_path}_audio.m4a",
                    remove_temp=True,
                    logger=None # Suppress progress bar to console
                )

            # Read output back into BytesIO
            with open(temp_out_path, "rb") as f:
                output_bytes = io.BytesIO(f.read())
                output_bytes.name = filename # Preserve original name

            return output_bytes

        except Exception as e:
            logging.exception("Failed to optimize video %s: %s", filename, e)
            st.error(f"Video optimization failed: {e}")
            return None

        finally:
            # Cleanup temp files
            for path in [temp_in_path, temp_out_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
