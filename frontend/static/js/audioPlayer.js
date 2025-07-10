class AudioPlayer {
    constructor() {
        this.audio = document.getElementById('audio');
        this.queue = window.queue;
        this.currentIndex = 0;
        this.isPlaying = false;
        
        // Bind event listeners
        this.audio.addEventListener('ended', () => this.handleTrackEnd());
        this.audio.addEventListener('loadedmetadata', () => this.handleMetadataLoaded());
        this.audio.addEventListener('play', () => this.handlePlay());
        this.audio.addEventListener('pause', () => this.handlePause());
        this.audio.addEventListener('error', (e) => this.handleError(e));
    }

    // Load a track by index
    loadTrack(index) {
        if (index < 0 || index >= this.queue.length() || this.queue.length() === 0) {
            console.warn('Invalid track index or empty queue');
            return false;
        }

        this.currentIndex = index;
        const track = this.queue.items[index];
        this.audio.src = track.url || track.src || track.file;
        this.audio.load();
        
        return true;
    }

    play() {
        if (this.queue.length() === 0) {
            console.warn('No tracks in queue');
            return false;
        }

        // If no track is loaded, load the first one
        if (!this.audio.src && this.queue.length() > 0) {
            this.loadTrack(0);
        }

        const playPromise = this.audio.play();
        
        if (playPromise !== undefined) {
            playPromise.catch(error => {
                console.error('Error playing audio:', error);
            });
        }
        
        return true;
    }

    pause() {
        this.audio.pause();
    }

    togglePlay() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    next() {
        if (this.queue.length() === 0) {
            console.warn('No tracks in queue');
            return false;
        }

        const nextIndex = this.currentIndex + 1;
        
        if (nextIndex < this.queue.length()) {
            this.loadTrack(nextIndex);
            if (this.isPlaying) {
                console.log("Starting to play next track");
                console.log(this);
                this.play();
            }
            return true;
        } else {
            console.log('End of queue reached');
            return false;
        }
    }

    previous() {
        // if (this.queue.length() === 0) {
        //     console.warn('No tracks in queue');
        //     return false;
        // }

        // const prevIndex = this.currentIndex - 1;
        
        // if (prevIndex >= 0) {
        //     this.loadTrack(prevIndex);
        //     if (this.isPlaying) {
        //         this.play();
        //     }
        //     return true;
        // } else {
        //     // If at beginning, restart current track
        //     this.audio.currentTime = 0;
        //     if (this.isPlaying) {
        //         this.play();
        //     }
        //     return false;
        // }
        debugger;
        if (this.queue.length() === 0) {
            console.warn('No tracks in queue');
            return false;
        }

        // If track has played for more than 10 seconds, restart current track
        if (this.audio.currentTime > 5) {
            this.audio.currentTime = 0;
            if (this.isPlaying) {
                this.play();
            }
            return true;
        }

        // If track has played for less than 10 seconds, go to previous track
        const prevIndex = this.currentIndex - 1;
        
        if (prevIndex >= 0) {
            this.loadTrack(prevIndex);
            if (this.isPlaying) {
                this.play();
            }
            return true;
        } else {
            // If at beginning and less than 10 seconds, restart current track
            this.audio.currentTime = 0;
            if (this.isPlaying) {
                this.play();
            }
            return false;
        }
    }

    // Jump to a specific track in the queue
    playTrack(index) {
        if (this.loadTrack(index)) {
            this.play();
            return true;
        }
        return false;
    }

    // Get current track info
    getCurrentTrack() {
        if (this.currentIndex >= 0 && this.currentIndex < this.queue.length()) {
            return this.queue.items[this.currentIndex];
        }
        return null;
    }

    // Get current index
    getCurrentIndex() {
        return this.currentIndex;
    }

    // Check if player is playing
    getIsPlaying() {
        return this.isPlaying;
    }

    // Event handlers
    handleTrackEnd() {
        console.log('Track ended');
        this.isPlaying = true;
        // Try to play next track
        if (!this.next()) {
            // If no next track, pause the player
            this.isPlaying = false;
            console.log('End of queue reached, pausing player');
        }
    }

    handleMetadataLoaded() {
        console.log('Track metadata loaded:', this.getCurrentTrack());
    }

    handlePlay() {
        this.isPlaying = true;
        console.log('Playback started');
    }

    handlePause() {
        this.isPlaying = false;
        console.log('Playback paused');
    }

    handleError(error) {
        console.error('Audio error:', error);
        this.isPlaying = false;
    }

    // Update current index when queue is modified externally
    updateCurrentIndex(newIndex) {
        if (newIndex >= 0 && newIndex < this.queue.length()) {
            this.currentIndex = newIndex;
        }
    }

    // Reset player
    reset() {
        this.pause();
        this.currentIndex = 0;
        this.audio.src = '';
        this.isPlaying = false;
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

// Example usage:
// const audioElement = document.getElementById('audio');
// const queue = new Queue(); // Your existing queue instance
// const player = new AudioPlayer(audioElement, queue);

// Add some songs to the queue (example structure)
// queue.push({ title: 'Song 1', artist: 'Artist 1', url: 'path/to/song1.mp3' });
// queue.push({ title: 'Song 2', artist: 'Artist 2', url: 'path/to/song2.mp3' });

// Attach to UI buttons
// document.getElementById('play-pause-btn').onclick = () => player.togglePlay();
// document.getElementById('next-btn').onclick = () => player.next();
// document.getElementById('previous-btn').onclick = () => player.previous();