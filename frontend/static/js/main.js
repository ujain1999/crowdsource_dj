const queue = new Queue();
window.queue = queue;
const draggableTable = new DraggableTable('queue-div', queue);
window.draggableTable = draggableTable;
const player = new AudioPlayer();
window.player = player;


const isValidURL = (str) => {
  try {
    new URL(str);
    return true;
  } catch (e) {
        return false;
  }
}

const isPlaylist = (str) => {
    const urlParams = new URLSearchParams(str);
    if (urlParams.get('list')){
        return urlParams.get('list')
    }
    else {
        return false;
    }
}

const fetchData = () => {
    const inputValue = document.getElementById("search-or-url-input").value
    if (inputValue != ''){
        fetch("/api/search", {
            method: "POST",
            body: JSON.stringify({
                type : isValidURL(inputValue) ? "url" : "query",
                inputText : inputValue,
                playlist : isPlaylist(inputValue),
                room_id : location.pathname.slice(1)
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8"
            }
        })
        .then((response) => response.json())
        .then((data) => {
            queue.push(data)
            console.log(queue)
        });
    }
    // console.log(queue)
}

const initialFetch = () => {
    const room_id = location.pathname.slice(1);
    fetch("/api/queue", {
        method: "POST",
        body: JSON.stringify({
            "room_id" : room_id
        }),
        headers: {
            "Content-type": "application/json; charset=UTF-8"
        }
    })
    .then((response) => response.json())
    .then((data) => {
        console.log(data);
        if (data.hasOwnProperty('queue')){
            if (data['queue'].length > 0){
                queue.items = data['queue'];
            }
        }
        console.log(queue);
    });
}

window.onload = initialFetch();

document.getElementById('search-btn').addEventListener('click', fetchData);
document.getElementById('play-pause').onclick = () => player.togglePlay();
document.getElementById('next').onclick = () => player.next();
document.getElementById('previous').onclick = () => player.previous();

const audio = document.getElementById('audio');

audio.addEventListener('play', updatePlayPauseUI);
audio.addEventListener('pause', updatePlayPauseUI);
audio.addEventListener('timeupdate', updateProgressUI);
audio.addEventListener('loadedmetadata', updateDurationUI);

document.getElementById('progress').addEventListener('input', (e) => {
  audio.currentTime = e.target.value;
});