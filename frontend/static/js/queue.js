class Queue {
    constructor() {
        this._queue = [];
    }

    get items() {
        return this._queue;
    }

    set items(newQueue) {
        this._queue = newQueue;
        // this.onUpdate();
        this.onUpdate();
    }

    length() {
        return this._queue.length
    }

    push(item) {
        this._queue.push(item);
        // this.onUpdate();
        this.onUpdate();
    }

    onUpdate() {
        const queueDiv = document.getElementById('queue-div');

        if (!this.length) {
            queueDiv.innerHTML = ""
            return
        }
        else {
            const tableHTML = `
                    <table id="draggableTable" class="u-full-width">
                        <thead id="queue-thead" class="sticky">
                            <tr>
                                <th></th>
                                <th>Title</th>
                                <th>Artist</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this._queue.map((song, index) => `
                                <tr draggable="true" data-index="${index}">
                                    <td class="drag-handle">⋮⋮</td>
                                    <td>${song.title}</td>
                                    <td>${song.artist}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;

            queueDiv.innerHTML = tableHTML;

            // Re-initialize drag functionality after rendering
            if (window.draggableTable) {
                window.draggableTable.initializeDragHandlers();
            }
        }
    }
}
