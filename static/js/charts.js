window.formatIndian = (value) => {
  const numeric = Number(value || 0);
  if (Number.isNaN(numeric)) {
    return "0";
  }
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(numeric);
};

window.buildLineChart = (canvasId, labels, datasets, options = {}) => {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") {
    return null;
  }

  return new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          position: "top",
        },
      },
      ...options,
    },
  });
};

window.buildBarChart = (canvasId, labels, values, label, colors = ["#1a3a5c"], options = {}) => {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") {
    return null;
  }

  return new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label,
          data: values,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        },
      },
      scales: {
        y: {
          ticks: {
            callback: (value) => window.formatIndian(value),
          },
        },
      },
      ...options,
    },
  });
};

window.buildDoughnutChart = (canvasId, labels, values, colors, options = {}) => {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") {
    return null;
  }

  return new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: colors,
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
        },
      },
      ...options,
    },
  });
};

window.buildRevenueTrendChart = (canvasId, labels, revenueData, invoiceData) => window.buildLineChart(canvasId, labels, [
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
], {
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
});
