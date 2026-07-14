function tickClock() {
  const el = document.getElementById("liveClock");
  if (!el) return;
  const now = new Date();
  const pad = (n) => n.toString().padStart(2, "0");
  el.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

if (document.getElementById("liveClock")) {
  tickClock();
  setInterval(tickClock, 1000);
}
