document.getElementById("new-room-btn").addEventListener("click", () => {
    fetch("/api/room", {
            method: "POST",
            body: JSON.stringify({'action' : 'create'}),
            headers: {"Content-type": "application/json; charset=UTF-8"}
        })
        .then((response) => response.json())
        .then((data) => {
            location.href = '/' + data.room_id;
            console.log(queue)
        });
})