class AudioPlayer {
    constructor(queue) {
        this.queue = queue;
        this.currentIndex = 0;
        this.audio = this.audio = document.getElementById('audio');
        this.isPlaying = false;

        // Listen to queue changes
        this.queue.onUpdate(() => {
            if (this.currentIndex >= this.queue.length()) {
                this.currentIndex = 0;
            }
            this.loadCurrent();
        });

        this.audio.addEventListener('ended', () => {
            this.next();
        });
    }

    loadCurrent() {
        debugger;
        const currentTrack = this.queue.items[this.currentIndex];
        if (!currentTrack) return;

        const url = typeof currentTrack === 'string' ? currentTrack : currentTrack.url;
        this.audio.src = url;
        this.audio.load();
    }

    play() {
        if (!this.audio.src) this.loadCurrent();
        this.audio.play();
        this.isPlaying = true;
    }

    pause() {
        this.audio.pause();
        this.isPlaying = false;
    }

    togglePlayPause() {
        this.isPlaying ? this.pause() : this.play();
    }

    next() {
        if (this.currentIndex < this.queue.length() - 1) {
            this.currentIndex++;
            this.loadCurrent();
            this.play();
        } else {
            // Reached end of queue — stop playback
            this.audio.pause();
            this.audio.currentTime = 0;
            this.isPlaying = false;
        }
    }

    prev() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.loadCurrent();
            this.play();
        }
    }

    getCurrentTrack() {
        return this.queue.items[this.currentIndex];
    }
}

function updatePlayPauseUI() {
    const btn = document.getElementById('play-pause');
    if (audio.paused) {
        // btn.textContent = 'Play';
        btn.innerHTML = `<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" clip-rule="evenodd"><path d="M23 12l-22 12v-24l22 12zm-21 10.315l18.912-10.315-18.912-10.315v20.63z"/></svg>`
    } else {
        // btn.textContent = 'Pause';
        btn.innerHTML = `<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" clip-rule="evenodd"><path d="M10 24h-6v-24h6v24zm10 0h-6v-24h6v24zm-11-23h-4v22h4v-22zm10 0h-4v22h4v-22z"/></svg>`
    }
}

function updateProgressUI() {
    const progressBar = document.getElementById('progress');
    progressBar.value = audio.currentTime;
    const currTime = document.getElementById("current-time");
    const date = new Date(null);
    date.setSeconds(audio.currentTime) // specify value for SECONDS here
    currTime.innerHTML = date.toISOString().slice(14, 19);
}


function updateDurationUI() {
    document.getElementById('progress').max = audio.duration;
    const duration = document.getElementById("duration");
    const date = new Date(null);
    date.setSeconds(audio.duration);
    duration.innerHTML = date.toISOString().slice(14,19);
}

function handleTrackEnd() {
    player.next(); // or show replay button, etc.
}