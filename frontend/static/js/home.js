document.getElementById("new-room-btn").addEventListener("click", () => {
    fetch("/api/room", {
        method: "POST",
        body: JSON.stringify({ 'action': 'create' }),
        headers: { "Content-type": "application/json; charset=UTF-8" }
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.room_id.length == 12){
                const room_id = data.room_id.substring(0, 4) + '-' + data.room_id.substring(4, 8) + '-' + data.room_id.substring(8, 12);
                location.href = '/' + room_id;
            }
            else{
                location.href = '/' + data.room_id;
            }
        });
})

document.getElementById("join-room-btn").addEventListener("click", () => {
    location.href = '/' + document.getElementById("room-id-input").value;
})

const roomIdInput = document.getElementById('room-id-input');
const charCountSpan = document.getElementById('char-count');

const  formatRoomId = (value) => {
    const cleaned = value.replace(/[^A-Za-z0-9]/g, '').toLowerCase();
    const limited = cleaned.substring(0, 12);
    const formatted = limited.replace(/(.{4})/g, '$1-').replace(/-$/, '');
    return formatted;
}

roomIdInput.addEventListener('input', (e) => {
    const cursorPosition = e.target.selectionStart;
    const oldValue = e.target.value;
    const newValue = formatRoomId(e.target.value);

    // Count hyphens before cursor in old value
    const hyphensBeforeCursor = (oldValue.substring(0, cursorPosition).match(/-/g) || []).length;
    // Set the new formatted value
    e.target.value = newValue;
    // Count hyphens before cursor in new value
    const newHyphensBeforeCursor = (newValue.substring(0, cursorPosition).match(/-/g) || []).length;
    // Adjust cursor position based on hyphen changes
    const newCursorPosition = cursorPosition + (newHyphensBeforeCursor - hyphensBeforeCursor);
    // Set cursor position, ensuring it doesn't go beyond the value length
    e.target.setSelectionRange(
        Math.min(newCursorPosition, newValue.length),
        Math.min(newCursorPosition, newValue.length)
    );
    // Update character count (without hyphens)
    const cleanValue = newValue.replace(/-/g, '');
});

// Handle paste events
roomIdInput.addEventListener('paste', (e) => {
    setTimeout(() => {
        const formatted = formatRoomId(e.target.value);
        e.target.value = formatted;
        const cleanValue = formatted.replace(/-/g, '');
    }, 0);
});

// Prevent typing hyphens manually
roomIdInput.addEventListener('keydown', (e) => {
    if (e.key === '-') {
        e.preventDefault();
        const cursorPosition = e.target.selectionStart;
        console.log(cursorPosition);
        if (cursorPosition == 4 || cursorPosition == 9){
            e.target.value = e.target.value + '-';
        }
    }
});