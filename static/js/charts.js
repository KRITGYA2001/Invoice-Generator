window.buildRevenueTrendChart = (canvasId, labels, revenueData, invoiceData) => {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") {
    return null;
  }

  return new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Revenue",
          data: revenueData,
          borderColor: "#1a3a5c",
          backgroundColor: "rgba(26,58,92,0.15)",
          tension: 0.3,
          yAxisID: "y",
          fill: true,
        },
        {
          label: "Invoices",
          data: invoiceData,
          borderColor: "#c8832a",
          backgroundColor: "rgba(200,131,42,0.12)",
          tension: 0.2,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      scales: {
        y: {
          type: "linear",
          position: "left",
          ticks: {
            callback: (value) => window.formatIndian(value),
          },
        },
        y1: {
          type: "linear",
          position: "right",
          grid: {
            drawOnChartArea: false,
          },
        },
      },
      plugins: {
        legend: {
          position: "top",
        },
      },
    },
  });
};
