document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
    document.querySelectorAll(".alert").forEach((el) => {
      el.style.transition = "opacity 0.3s";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    });
  }, 4000);
});

document.body.addEventListener("htmx:confirm", (e) => {
  if (!confirm(e.detail.question)) {
    e.preventDefault();
  }
});

document.addEventListener("htmx:beforeRequest", () => {
  if (document.getElementById("page-loader")) {
    return;
  }
  const loader = document.createElement("div");
  loader.className = "page-loader";
  loader.id = "page-loader";
  document.body.appendChild(loader);
});

document.addEventListener("htmx:afterRequest", () => {
  const loader = document.getElementById("page-loader");
  if (loader) {
    loader.remove();
  }
});

window.formatIndian = (num) => {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(num);
};
