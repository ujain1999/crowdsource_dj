class DraggableTable {
    constructor(containerDivId, queue) {
        this.containerDiv = document.getElementById(containerDivId);
        this.queue = queue;
        this.draggedRow = null;
        this.draggedIndex = null;
        this.isUpdatingFromDrag = false; // Flag to prevent circular updates
        this.init();
    }

    init() {
        // Initial render will be handled by queue.onUpdate()
        this.initializeDragHandlers();
    }

    initializeDragHandlers() {
        console.log("Here");
        // Find the table within the container div
        const table = this.containerDiv.querySelector('#draggableTable');
        if (!table) return;

        // Add event listeners to all draggable rows
        const rows = table.querySelectorAll('tbody tr[draggable="true"]');

        rows.forEach(row => {
            // Remove existing listeners to prevent duplicates
            row.removeEventListener('dragstart', this.handleDragStart);
            row.removeEventListener('dragover', this.handleDragOver);
            row.removeEventListener('dragenter', this.handleDragEnter);
            row.removeEventListener('dragleave', this.handleDragLeave);
            row.removeEventListener('drop', this.handleDrop);
            row.removeEventListener('dragend', this.handleDragEnd);

            // Add event listeners
            row.addEventListener('dragstart', this.handleDragStart.bind(this));
            row.addEventListener('dragover', this.handleDragOver.bind(this));
            row.addEventListener('dragenter', this.handleDragEnter.bind(this));
            row.addEventListener('dragleave', this.handleDragLeave.bind(this));
            row.addEventListener('drop', this.handleDrop.bind(this));
            row.addEventListener('dragend', this.handleDragEnd.bind(this));
        });
    }

    handleDragStart(e) {
        this.draggedRow = e.currentTarget;
        this.draggedIndex = parseInt(this.draggedRow.dataset.index);

        // Store the row data
        e.dataTransfer.setData('text/html', this.draggedRow.outerHTML);
        e.dataTransfer.effectAllowed = 'move';

        // Add visual feedback
        setTimeout(() => {
            this.draggedRow.classList.add('dragging');
        }, 0);
    }

    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    }

    handleDragEnter(e) {
        e.preventDefault();

        if (e.currentTarget === this.draggedRow) return;

        const targetRow = e.currentTarget;
        const targetIndex = parseInt(targetRow.dataset.index);

        // Clear previous drag over states
        this.clearDragOverStates();

        // Determine if we should show drop indicator above or below
        if (targetIndex < this.draggedIndex) {
            targetRow.classList.add('drag-over');
        } else {
            targetRow.classList.add('drag-over-bottom');
        }
    }

    handleDragLeave(e) {
        // Only remove classes if we're leaving the row entirely
        if (!e.currentTarget.contains(e.relatedTarget)) {
            e.currentTarget.classList.remove('drag-over', 'drag-over-bottom');
        }
    }

    handleDrop(e) {
        e.preventDefault();

        if (e.currentTarget === this.draggedRow) return;

        const targetRow = e.currentTarget;
        const targetIndex = parseInt(targetRow.dataset.index);

        // Update the queue order
        this.updateQueueOrder(this.draggedIndex, targetIndex);

        // Clear drag states
        this.clearDragOverStates();
    }

    handleDragEnd(e) {
        this.draggedRow.classList.remove('dragging');
        this.clearDragOverStates();

        this.draggedRow = null;
        this.draggedIndex = null;
        this.isUpdatingFromDrag = false;
    }

    updateQueueOrder(fromIndex, toIndex) {
        // Set flag to prevent circular updates
        this.isUpdatingFromDrag = true;

        // Create a copy of the queue items
        const items = [...this.queue.items];

        // Remove the item from its current position
        const [movedItem] = items.splice(fromIndex, 1);

        // Insert the item at the new position
        items.splice(toIndex, 0, movedItem);

        // Update the queue (this will trigger onUpdate)
        this.queue.items = items;
        const currPlayingIndex = player.currentIndex;
        if (fromIndex == currPlayingIndex){
            player.currentIndex = toIndex;
        }
        else if (fromIndex < currPlayingIndex && toIndex < currPlayingIndex) {
            player.currentIndex = player.currentIndex
        }
        else if (fromIndex < currPlayingIndex && toIndex > currPlayingIndex) {
            player.currentIndex = player.currentIndex - 1;

        }
        else if (fromIndex > currPlayingIndex && toIndex < currPlayingIndex) {
            player.currentIndex = player.currentIndex + 1;
        }
        else if (fromIndex > currPlayingIndex && toIndex > currPlayingIndex) {
            player.currentIndex = player.currentIndex;
        }

        console.log(`Item moved from position ${fromIndex} to ${toIndex}`);
        console.log('Updated queue:', this.queue.items);
    }

    clearDragOverStates() {
        const table = this.containerDiv.querySelector('#draggableTable');
        if (!table) return;

        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.classList.remove('drag-over', 'drag-over-bottom');
        });
    }
}