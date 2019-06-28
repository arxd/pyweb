

export class WebMain {
	constructor() {
		window.addEventListener("beforeunload", () => {
            this.sock.close();
        });
	}
	
	async connect(cred) {
		let host = /https?:\/\/(.*?)\/.*/.exec(window.location)[1];
		let ws = "ws://" + host + '/ws';

		console.log("WS: Connecting as ", cred);
		return new Promise((resolve, reject) => {
			let sock = new WebSocket(ws);

			sock.onerror = (e) => {
				console.log("Socket Error:", e);
				//this.el.dispatchEvent(new CustomEvent('status', { detail:e.code }));
				if (this.sock) {
					delete this.sock;
					//main.on_disconnect(e.code); // notify the main that we are down
				} else {
					resolve({error:1});
				}
			}

			sock.onclose = (e) => {
				console.log("Closed", e);
				//this.el.dispatchEvent(new CustomEvent('status', { detail:e.code }));
				if (this.sock) {
					delete this.sock;
				} else {
					resolve({error:e.code});
				}
			};

			sock.onopen = (e) => {
				// we know we have an internet connection
				//this.el.dispatchEvent(new CustomEvent('status', { detail: 0 }));
				try {
					sock.send(JSON.stringify(cred));
				} catch(err) {
					resolve({error:err});
				}
			}

			sock.onmessage = async (e) => {
				if (this.sock) {
					let obj = JSON.parse(e.data);
					console.log("MSG:", obj);
					//this.el.dispatchEvent(new CustomEvent(obj.cmd, { detail: obj.args }));
				} else {
					// successful connection.  Send our database state
					this.sock = sock;
					resolve(JSON.parse(e.data));
				}
			}
		});
	}

	close() {
		if (this.sock)
			this.sock.close();
	}

	
	async onload() {
		let resp = await this.connect({id:Math.random()});
		console.log("Loaded", resp);
	}
	
}
