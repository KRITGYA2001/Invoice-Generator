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

window.buildBarChart = (canvasId, labels, values, label, colors = ["#f5c842"], options = {}) => {
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
    borderColor: "#f5c842",
    backgroundColor: "rgba(245,200,66,0.15)",
    tension: 0.3,
    yAxisID: "y",
    fill: true,
  },
  {
    label: "Invoices",
    data: invoiceData,
    borderColor: "#1f1f1f",
    backgroundColor: "rgba(31,31,31,0.12)",
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
