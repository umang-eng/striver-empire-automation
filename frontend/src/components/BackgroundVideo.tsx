"use client";

import { useEffect, useRef, useState } from "react";

export function BackgroundVideo() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (motionQuery.matches) {
      video.pause();
      return;
    }

    const attemptPlay = async () => {
      try {
        await video.play();
      } catch {
        // Autoplay blocked by browser policy; poster + ambient glass backdrop remains intact
      }
    };
    void attemptPlay();
  }, []);

  return (
    <div className="pointer-events-none fixed inset-0 -z-20 overflow-hidden bg-[#05070d]">
      {!videoFailed ? (
        <video
          ref={videoRef}
          className="h-full w-full scale-[1.01] object-cover object-center"
          src="/video/background.mp4"
          poster="/video/background-poster.jpg"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          aria-hidden="true"
          onError={() => setVideoFailed(true)}
        />
      ) : (
        <div
          className="h-full w-full bg-cover bg-center"
          style={{ backgroundImage: "url('/video/background-poster.jpg')" }}
          aria-hidden="true"
        />
      )}

      {/* Translucent dark scrim & radial ambient contrast layer for Apple Liquid Glass legibility */}
      <div
        className="absolute inset-0 bg-gradient-to-b from-black/55 via-black/45 to-black/75"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.08),transparent_60%)]"
        aria-hidden="true"
      />
    </div>
  );
}
