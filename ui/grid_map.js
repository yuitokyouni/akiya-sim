"use strict";
/** 格子マップ描画・東京都域 bounds（全 HTML ビュー共通） */
(function (root) {
  function eng() {
    if (!root.AkiyaEngine) throw new Error("Load engine.js before ui/grid_map.js");
    return root.AkiyaEngine;
  }

  function activeBounds(zone, W, H) {
    let minX = W - 1, maxX = 0, minY = H - 1, maxY = 0, any = false;
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        if (zone[y * W + x] < 0) continue;
        any = true;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
    if (!any) return { minX: 0, maxX: W - 1, minY: 0, maxY: H - 1, gw: W, gh: H };
    return { minX, maxX, minY, maxY, gw: maxX - minX + 1, gh: maxY - minY + 1 };
  }

  function gridToLngLat(x, y, A, W, H) {
    const lon = A.lon0 + (x / (W - 1)) * (A.lon1 - A.lon0);
    const lat = A.latN - (y / (H - 1)) * (A.latN - A.latS);
    return [lon, lat];
  }

  function dataBoundsLngLat(marginDeg) {
    const { W, H, zone, AFFINE } = eng();
    const m = marginDeg == null ? 0.012 : marginDeg;
    const B = activeBounds(zone, W, H);
    const sw = gridToLngLat(B.minX, B.maxY, AFFINE, W, H);
    const ne = gridToLngLat(B.maxX, B.minY, AFFINE, W, H);
    return [
      [sw[0] - m, sw[1] - m],
      [ne[0] + m, ne[1] + m],
    ];
  }

  function drawGridMap(cv, world, opts) {
    const { W, H, zone, COLORS } = eng();
    const B = activeBounds(zone, W, H);
    const pad = opts && opts.pad != null ? opts.pad : 12;
    const bg = (opts && opts.bg) || "#e8ecf0";
    const cx = cv.getContext("2d");
    const gw = B.gw;
    const gh = B.gh;
    const cw = (cv.width - pad * 2) / gw;
    const ch = (cv.height - pad * 2) / gh;

    cx.fillStyle = bg;
    cx.fillRect(0, 0, cv.width, cv.height);

    for (let y = B.minY; y <= B.maxY; y++) {
      for (let x = B.minX; x <= B.maxX; x++) {
        const i = y * W + x;
        if (zone[i] < 0) continue;
        cx.fillStyle = COLORS[world.st[i]];
        cx.fillRect(
          pad + (x - B.minX) * cw,
          pad + (y - B.minY) * ch,
          Math.max(1, cw - 0.5),
          Math.max(1, ch - 0.5),
        );
      }
    }

    if (opts && opts.stations) {
      cx.strokeStyle = (opts && opts.stationColor) || "#22313a";
      cx.lineWidth = 1.5;
      for (const [sx, sy] of opts.stations) {
        if (sx < B.minX || sx > B.maxX || sy < B.minY || sy > B.maxY) continue;
        cx.beginPath();
        cx.arc(pad + (sx - B.minX + 0.5) * cw, pad + (sy - B.minY + 0.5) * ch, 4, 0, 7);
        cx.stroke();
      }
    }
  }

  function aspectRatio() {
    const { W, H, zone } = eng();
    const B = activeBounds(zone, W, H);
    return B.gw / B.gh;
  }

  function cellFromEvent(cv, ev, pad) {
    const { W, H, zone } = eng();
    const B = activeBounds(zone, W, H);
    const p = pad == null ? 12 : pad;
    const rect = cv.getBoundingClientRect();
    const sx = (ev.clientX - rect.left) * (cv.width / rect.width);
    const sy = (ev.clientY - rect.top) * (cv.height / rect.height);
    const gw = B.gw;
    const gh = B.gh;
    const cw = (cv.width - p * 2) / gw;
    const ch = (cv.height - p * 2) / gh;
    const gx = Math.floor((sx - p) / cw) + B.minX;
    const gy = Math.floor((sy - p) / ch) + B.minY;
    if (gx < B.minX || gx > B.maxX || gy < B.minY || gy > B.maxY) return null;
    const i = gy * W + gx;
    if (zone[i] < 0) return null;
    return { i, gx, gy, B };
  }

  root.GridMapUI = { activeBounds, gridToLngLat, dataBoundsLngLat, drawGridMap, aspectRatio, cellFromEvent };
})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this);
