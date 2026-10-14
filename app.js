document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-table-search]").forEach(input => {
    input.addEventListener("input", () => {
      const table = document.getElementById(input.dataset.tableSearch);
      if (!table) return;
      const query = input.value.toLowerCase();
      table.querySelectorAll("tbody tr").forEach(row => {
        row.hidden = !row.innerText.toLowerCase().includes(query);
      });
    });
  });
  document.querySelectorAll(".flash").forEach(flash => {
    setTimeout(() => { flash.style.opacity = "0"; setTimeout(() => flash.remove(), 350); }, 4500);
  });
});
