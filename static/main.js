function main() {
    let ws = new WebSocket('ws://localhost:8080/ws')
    let pc = new RTCPeerConnection()

    window.pc = pc
    window.ws = ws

    let description_set = false
    let pending_candidates = []

    pc.ontrack = (track) => {
        let stream = track.streams[0]
        let video = document.querySelector('video')
        video.srcObject = stream
    }

    pc.onicecandidate = (event) => {
        console.log("pc.onicecandidate")
        if (event.candidate && event.candidate.candidate) {
            ws.send(JSON.stringify({
                'action': 'ice-candidate',
                'candidate': {
                    'mline': event.candidate.sdpMLineIndex,
                    'candidate': event.candidate.candidate
                }
            }))
        }
    }

    ws.onopen = () => {
        ws.send(JSON.stringify({
            'action': 'connect',
            'ip': '127.0.0.1'
        }))
    }

    ws.onmessage = (event) => {
        let data = JSON.parse(event.data)
        console.log("onmessage")
        console.log(data)
        if (data['action'] == 'set-description') {
            pc.setRemoteDescription({
                type: data['desc']['type'],
                sdp: data['desc']['sdp']
            }).then(() => {
                return pc.createAnswer({
                    'offerToReceiveAudio': true,
                    'offerToReceiveVideo': true,
                })
            }).then((answer) => {
                pc.setLocalDescription(answer)
                ws.send(JSON.stringify({
                    'action': 'set-description',
                    'desc': {
                        'type': answer.type,
                        'sdp': answer.sdp
                    }
                }))
                description_set = true
                for (let candidate of pending_candidates) {
                    pc.addIceCandidate({
                        "sdpMLineIndex": candidate['mline'],
                        "candidate": candidate['candidate']
                    })
                }
                pending_candidates = []
            })
        } else if (data['action'] == 'ice-candidate') {
            console.log("got ice candidate")
            if (description_set) {
                pc.addIceCandidate({
                    "sdpMLineIndex": data['candidate']['mline'],
                    "candidate": data['candidate']['candidate']
                })
            } else {
                pending_candidates.push(data['candidate'])
            }
        }

    }
}

window.onload = main