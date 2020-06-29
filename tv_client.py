from threading import Thread
import asyncio
import logging

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp  # noqa
from gi.repository import GstWebRTC  # noqa
from gi.repository import Gst  # noqa


PIPELINE_DESC = '''
webrtcbin name=sendrecv bundle-policy=max-bundle
 videotestsrc is-live=true pattern=ball ! videoconvert ! queue ! vp8enc deadline=1 ! rtpvp8pay !
 queue ! application/x-rtp,media=video,encoding-name=VP8,payload=97 ! sendrecv.
 audiotestsrc is-live=true wave=red-noise ! audioconvert ! audioresample ! queue ! opusenc ! rtpopuspay !
 queue ! application/x-rtp,media=audio,encoding-name=OPUS,payload=96 ! sendrecv.
'''


class GstThread(Thread):
    def __init__(self):
        super().__init__()
        self.gst_loop = None

    def run(self):
        Gst.init(None)
        self.gst_loop = asyncio.new_event_loop()
        self.gst_loop.run_forever()


class GstWebrtcClient:
    def __init__(self, tvclient):
        self.pipe = None
        self.webrtc = None
        self.tvclient = tvclient

    def startPipeline(self):
        logging.info("GstWebrtcClient.startPipeline")
        self.pipe = Gst.parse_launch(PIPELINE_DESC)
        self.webrtc = self.pipe.get_by_name("sendrecv")
        self.webrtc.connect('on-negotiation-needed',
                            self.onNegotiationNeeded)
        self.webrtc.connect('on-ice-candidate', self.onIceCandidate)
        self.webrtc.connect('notify::connection-state', self.onIceStateChanged)
        self.webrtc.connect('notify::signaling-state',
                            self.onSignalingStateChanged)
        self.webrtc.connect('notify::connection-state',
                            self.onConnectionStateChanged)
        self.pipe.set_state(Gst.State.PLAYING)

    def stop(self):
        logging.info("GstWebrtcClient.stop")
        self.pipe.set_state(Gst.State.NULL)
        self.pipe = None
        self.webrtc = None

    def setRemoteDescription(self, desc):
        sdp = desc['sdp']
        t = GstWebRTC.WebRTCSDPType.ANSWER
        if (desc['type'] == 'offer'):
            t = GstWebRTC.WebRTCSDPType.OFFER
        _, sdpmsg = GstSdp.SDPMessage.new()
        GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
        answer = GstWebRTC.WebRTCSessionDescription.new(t, sdpmsg)
        promise = Gst.Promise.new_with_change_func(
            self.onRemoteAnswerSet, None)
        self.webrtc.emit('set-remote-description', answer, promise)

    def addIceCandidate(self, mline, candidate):
        logging.info("GstWebrtcClient.addIceCandidate")
        self.webrtc.emit('add-ice-candidate', mline, candidate)

    def onNegotiationNeeded(self, webrtc):
        logging.info("GstWebrtcClient.onNegotiationNeeded")
        promise = Gst.Promise.new_with_change_func(
            self.onOfferCreated, None)
        webrtc.emit('create-offer', None, promise)

    def onOfferCreated(self, promise, _):
        promise.wait()
        logging.info("GstWebrtcClient.onOfferCreated")
        result = promise.get_reply()
        promise = Gst.Promise.new_with_change_func(
            self.onLocalOfferSet, None)
        self.webrtc.emit('set-local-description',
                         result.get_value('offer'), promise)

    def onLocalOfferSet(self, promise, _):
        promise.wait()
        logging.info("GstWebrtcClient.onLocalOfferSet")
        self.tvclient.onLocalDescription(
            self.webrtc.props.local_description.type.value_nick,
            self.webrtc.props.local_description.sdp.as_text()
        )

    def onRemoteAnswerSet(self, promise, _):
        promise.wait()
        logging.info("GstWebrtcClient.onRemoteAnswerSet")

    def onIceCandidate(self, webrtc, mline_index, candidate):
        logging.info("GstWebrtcClient.onIceCandidate")
        self.tvclient.onIceCandidate(mline_index, candidate)

    def onIceStateChanged(self, webrtc, _):
        logging.info("onIceStateChanged: %s",
                     webrtc.props.ice_connection_state)

    def onSignalingStateChanged(self, webrtc, _):
        logging.info("onSignalingStateChanged: %s",
                     webrtc.props.signaling_state)

    def onConnectionStateChanged(self, webrtc, _):
        logging.info("onConnectionStateChanged: %s",
                     webrtc.props.connection_state)


class TvClient:
    def __init__(self, loop, gst_loop):
        self.sendQueue = asyncio.Queue(loop=loop)
        self.ip = None
        self.webrtc = GstWebrtcClient(self)
        self.loop = loop
        self.gst_loop = gst_loop

    def stop(self):
        logging.info("TvClient.stop")
        self.loop.call_soon_threadsafe(self.stopQueue)
        self.gst_loop.call_soon_threadsafe(self.webrtc.stop)

    def stopQueue(self):
        self.sendQueue.put_nowait(None)

    def setIp(self, ip):
        self.ip = ip
        self.gst_loop.call_soon_threadsafe(self.webrtc.startPipeline)

    def setRemoteDescription(self, desc):
        self.gst_loop.call_soon_threadsafe(
            self.webrtc.setRemoteDescription, desc)
        # self.webrtc.setRemoteDescription(desc)

    def addIceCandidate(self, mline, candidate):
        self.gst_loop.call_soon_threadsafe(
            self.webrtc.addIceCandidate, mline, candidate)
        # self.webrtc.addIceCandidate(mline, candidate)

    def onIceCandidate(self, mline_index, candidate):
        self.loop.call_soon_threadsafe(
            self.sendIceCandidate, mline_index, candidate)

    def sendIceCandidate(self, mline_index, candidate):
        self.sendQueue.put_nowait({
            'action': 'ice-candidate',
            'candidate': {
                'mline': mline_index,
                'candidate': candidate
            }
        })

    def onLocalDescription(self, t, sdp):
        # loop = asyncio.new_event_loop()
        self.loop.call_soon_threadsafe(self.sendLocalDescription, t, sdp)
        # loop.close()

    def sendLocalDescription(self, t, sdp):
        self.sendQueue.put_nowait({
            'action': 'set-description',
            'desc': {
                'type': t,
                'sdp': sdp
            }
        })
