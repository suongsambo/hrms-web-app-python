document.addEventListener("DOMContentLoaded", function () {
    fetch("/employees")
        .then(response => response.json())
        .then(data => {
            const list = document.getElementById("employeeList");
            data.forEach(emp => {
                let item = document.createElement("li");
                item.textContent = `${emp.name} - ${emp.department}`;
                list.appendChild(item);
            });
        });
});