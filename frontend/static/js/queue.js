class Queue {
    constructor() {
        this._queue = [];
    }

    get items() {
        return this._queue;
    }

    set items(newQueue) {
        this._queue = newQueue;
        this.onUpdate();
    }

    length() {
        return this._queue.length
    }

    push(item) {
        this._queue.push(item);
        this.onUpdate();
    }

    onUpdate() {
        console.log("Queue updated:", this._queue);
        const queueDiv = document.getElementById("queue-div");
        if (!this.length) {
            queueDiv.innerHTML = ""
            return
        }
        if (this.length) {
            const queueTable = document.createElement("table");
            queueTable.classList.add("u-full-width");
            const thead = document.createElement("thead");
            thead.id = "queue-thead"
            thead.classList.add("sticky")
            const headerRow = document.createElement("tr");
            headerRow.innerHTML = "<th></th><th>Title</th><th>Artist</th>";
            thead.appendChild(headerRow);
            queueTable.appendChild(thead);

            const tbody = document.createElement("tbody");
            this._queue.forEach((song, index) => {
                const row = document.createElement("tr");
                row.innerHTML = `<td>${index + 1}</td><td>${song.title}</td><td>${song.artist}</td>`;
                tbody.appendChild(row);
            });
            queueTable.appendChild(tbody);
            queueDiv.replaceChildren(queueTable);
            return;
        }
    }
}
