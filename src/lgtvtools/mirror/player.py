"""HTML player template generation for HLS streaming.

This module generates a minimal HTML page with hls.js that auto-plays
the HLS stream in the TV's webOS browser.
"""

from __future__ import annotations


def generate_player_html(stream_url: str) -> str:
    """Return an HTML page with hls.js that auto-plays the given m3u8 URL.

    The page:
    - Loads hls.js from CDN (https://cdn.jsdelivr.net/npm/hls.js@latest)
    - Creates a full-screen <video> element with autoplay and muted attributes
    - Handles native HLS support (Safari) fallback
    - Auto-plays with muted audio (required by most browsers for autoplay)
    - Shows a simple error overlay if playback fails

    Args:
        stream_url: The full URL to the HLS playlist (e.g., http://192.168.1.x:PORT/stream.m3u8)

    Returns:
        A complete HTML document string ready to be served to the TV browser.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Screen Mirror</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            background: #000;
            overflow: hidden;
        }}
        video {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        #error-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            color: #fff;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            z-index: 1000;
        }}
        #error-overlay.visible {{
            display: flex;
        }}
        #error-overlay h1 {{
            font-size: 2em;
            margin-bottom: 0.5em;
            color: #ff6b6b;
        }}
        #error-overlay p {{
            font-size: 1.2em;
            color: #ccc;
            text-align: center;
            max-width: 80%;
        }}
    </style>
</head>
<body>
    <video id="video" autoplay muted playsinline></video>
    <div id="error-overlay">
        <h1>Playback Error</h1>
        <p id="error-message">Unable to play the stream. Please check the connection.</p>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script>
        (function() {{
            var video = document.getElementById('video');
            var errorOverlay = document.getElementById('error-overlay');
            var errorMessage = document.getElementById('error-message');
            var streamUrl = '{stream_url}';

            function showError(message) {{
                errorMessage.textContent = message;
                errorOverlay.classList.add('visible');
            }}

            function hideError() {{
                errorOverlay.classList.remove('visible');
            }}

            if (Hls.isSupported()) {{
                var hls = new Hls({{
                    enableWorker: true,
                    lowLatencyMode: true,
                    backBufferLength: 30
                }});

                hls.loadSource(streamUrl);
                hls.attachMedia(video);

                hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                    hideError();
                    video.play().catch(function(err) {{
                        console.warn('Autoplay blocked:', err);
                    }});
                }});

                hls.on(Hls.Events.ERROR, function(event, data) {{
                    console.error('HLS error:', data);
                    if (data.fatal) {{
                        switch (data.type) {{
                            case Hls.ErrorTypes.NETWORK_ERROR:
                                showError('Network error - stream may have ended or is unreachable.');
                                hls.startLoad();
                                break;
                            case Hls.ErrorTypes.MEDIA_ERROR:
                                showError('Media error - attempting recovery...');
                                hls.recoverMediaError();
                                break;
                            default:
                                showError('Fatal error - unable to recover.');
                                hls.destroy();
                                break;
                        }}
                    }}
                }});
            }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                // Native HLS support (Safari)
                video.src = streamUrl;
                video.addEventListener('loadedmetadata', function() {{
                    hideError();
                    video.play().catch(function(err) {{
                        console.warn('Autoplay blocked:', err);
                    }});
                }});
                video.addEventListener('error', function() {{
                    showError('Video playback error.');
                }});
            }} else {{
                showError('HLS is not supported in this browser.');
            }}
        }})();
    </script>
</body>
</html>"""
