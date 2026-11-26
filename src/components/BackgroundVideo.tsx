"use client";

import { useEffect, useRef, useState } from "react";

export function BackgroundVideo() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Ensure DOM properties required by Safari/Chrome for continuous muted autoplay
    video.muted = true;
    video.defaultMuted = true;
    video.loop = true;
    video.playsInline = true;
    video.controls = false;
    video.disablePictureInPicture = true;
    video.setAttribute("controlsList", "nodownload nofullscreen noremoteplayback noplaybackrate");
    video.setAttribute("disableRemotePlayback", "");

    const forcePlay = () => {
      if (video.paused && !videoFailed) {
        void video.play().catch(() => {
          // Will retry on next interaction or canplay event
        });
      }
    };

    forcePlay();

    const handlePause = () => {
      // Enforce non-pausable live loop
      window.requestAnimationFrame(forcePlay);
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        forcePlay();
      }
    };

    video.addEventListener("canplay", forcePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("ended", forcePlay);
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("pointerdown", forcePlay, { passive: true });
    window.addEventListener("keydown", forcePlay, { passive: true });

    return () => {
      video.removeEventListener("canplay", forcePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("ended", forcePlay);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("pointerdown", forcePlay);
      window.removeEventListener("keydown", forcePlay);
    };
  }, [videoFailed]);

  return (
    <div
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#05070d] select-none"
      style={{
        userSelect: "none",
        WebkitUserSelect: "none",
        WebkitTouchCallout: "none",
      }}
      onContextMenu={(e) => e.preventDefault()}
      onDragStart={(e) => e.preventDefault()}
      aria-hidden="true"
    >
      {!videoFailed ? (
        <video
          ref={videoRef}
          className="pointer-events-none h-full w-full scale-[1.01] object-cover object-center select-none"
          style={{
            userSelect: "none",
            WebkitUserSelect: "none",
            WebkitTouchCallout: "none",
          }}
          src="/video/background.mp4"
          poster="/video/background-poster.jpg"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          controls={false}
          disablePictureInPicture
          controlsList="nodownload nofullscreen noremoteplayback noplaybackrate"
          draggable={false}
          tabIndex={-1}
          aria-hidden="true"
          onContextMenu={(e) => e.preventDefault()}
          onDragStart={(e) => e.preventDefault()}
          onError={() => setVideoFailed(true)}
        />
      ) : (
        <div
          className="pointer-events-none h-full w-full bg-cover bg-center select-none"
          style={{ backgroundImage: "url('/video/background-poster.jpg')" }}
        />
      )}

      {/* Protective transparent shield + translucent dark scrim for Liquid Glass readability */}
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/35 via-black/25 to-black/55 select-none"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.08),transparent_60%)] select-none"
        aria-hidden="true"
      />
    </div>
  );
}
