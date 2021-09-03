import enum
import os
from azure.eventgrid import EventGridEvent
from azure.eventgrid._generated.models import SubscriptionValidationEventData, \
    AcsRecordingFileStatusUpdatedEventData, AcsRecordingChunkInfoProperties
from BlobStorageHelper import BlobStorageHelper
from ConfigurationManager import ConfigurationManager
from Logger import Logger
from flask import json
import ast
from aiohttp import web
from azure.communication.callingserver._callingserver_client import CallingServerClient

CALL_RECORDING_ACTIVE_ERROR_CODE = "8553"
CALL_RECODING_NOT_FOUND_ERROR_CODE = "8522"
INVALID_JOIN_IDENTITY_ERROR_CODE = "8527"
CALL_NOT_ESTABLISHED_ERROR_CODE = "8501"
CALL_RECORDING_ACTIVE_ERROR = "Recording is already in progress, one recording can be active at one time."
configuration_manager = ConfigurationManager.get_instance()
connection_string = configuration_manager.get_app_settings("Connectionstring")
blob_connection_string = configuration_manager.get_app_settings(
    "BlobStorageConnectionString")
container_name = configuration_manager.get_app_settings("ContainerName")
calling_server_client = CallingServerClient.from_connection_string(
    connection_string)
call_back_uri = configuration_manager.get_app_settings('CallbackUri')
blob_storage_account_name = configuration_manager.get_app_settings(
    'BlobStorageAccountName')
blob_storage_account_key = configuration_manager.get_app_settings(
    'BlobStorageAccountKey')
recording_data = {}


class OperationStatus(enum.Enum):
    FAIL = 0,
    SUCCESS = 1


class CallRecordingController():

    def __init__(self):
        app = web.Application()
        app.add_routes(
            [web.get('/startRecording', CallRecordingController.start_recording)])
        app.add_routes(
            [web.get('/pauseRecording', CallRecordingController.pause_recording)])
        app.add_routes(
            [web.get('/resumeRecording', CallRecordingController.resume_recording)])
        app.add_routes(
            [web.get('/stopRecording', CallRecordingController.stop_recording)])
        app.add_routes(
            [web.get('/getRecordingState', CallRecordingController.get_recording_state)])
        app.add_routes(
            [web.post('/getRecordingFile', CallRecordingController.get_recording_file)])
        app.add_routes(
            [web.get('/getBlobSASUri', CallRecordingController.get_blob_sas_uri)])
        app.add_routes([web.get('/', CallRecordingController.startup)])
        web.run_app(app, port=5000)

    async def start_recording(request):
        try:
            server_call_id = request.rel_url.query['serverCallId']
            Logger.log_message(
                Logger.INFORMATION,
                'StartRecording called with serverCallId --> ' + server_call_id)

            if not server_call_id:
                return web.Response(text="serverCallId is invalid", status=400)

            res = calling_server_client.initialize_server_call(server_call_id).start_recording(server_call_id,
                                                                                               recording_state_callback_uri=call_back_uri)

            Logger.log_message(
                Logger.INFORMATION,
                "StartRecording response --> " + str(res) + ", Recording Id: " + res.recording_id)

            if server_call_id not in recording_data.keys():
                recording_data[server_call_id] = ''
            recording_data[server_call_id] = res.recording_id

            return web.Response(text=res.recording_id)
        except Exception as ex:
            Logger.log_message(
                Logger.ERROR, "Failed to start server recording --> " + str(ex))
            if CALL_RECORDING_ACTIVE_ERROR_CODE in str(ex) or \
               INVALID_JOIN_IDENTITY_ERROR_CODE in str(ex) or \
               CALL_NOT_ESTABLISHED_ERROR_CODE in str(ex):
                return web.Response(text=str(ex), status=400)

            return web.Response(text=str(ex), status=500)

    async def pause_recording(request):
        try:
            server_call_id = request.rel_url.query['serverCallId']
            recording_id = request.rel_url.query['recordingId']

            Logger.log_message(
                Logger.INFORMATION,
                'PauseRecording called with serverCallId --> ' + server_call_id + ' and recordingId --> ' + recording_id)

            if not server_call_id:
                return web.Response(text="serverCallId is invalid", status=400)

            if not recording_id:
                recording_id = recording_data[server_call_id]
                if not recording_id:
                    return web.Response(text="recordingId is invalid", status=400)
            elif server_call_id not in recording_data.keys():
                recording_data[server_call_id] = recording_id

            res = calling_server_client.initialize_server_call(server_call_id).pause_recording(server_call_id,
                                                                                               recording_id)

            Logger.log_message(Logger.INFORMATION,
                               "PauseRecording response --> " + str(res))
            return web.Response(text="OK")
        except Exception as ex:
            Logger.log_message(
                Logger.ERROR, "Failed to pause server recording --> " + str(ex))
            if CALL_RECODING_NOT_FOUND_ERROR_CODE in str(ex):
                return web.Response(text=str(ex), status=400)
            return web.Response(text=str(ex), status=500)

    async def resume_recording(request):
        try:
            server_call_id = request.rel_url.query['serverCallId']
            recording_id = request.rel_url.query['recordingId']

            Logger.log_message(
                Logger.INFORMATION,
                'ResumeRecording called with serverCallId --> ' + server_call_id + ' and recordingId --> ' + recording_id)

            if not server_call_id:
                return web.Response(text="serverCallId is invalid", status=400)

            if not recording_id:
                recording_id = recording_data[server_call_id]
                if not recording_id:
                    return web.Response(text="recordingId is invalid", status=400)
            elif server_call_id not in recording_data.keys():
                recording_data[server_call_id] = recording_id

            res = calling_server_client.initialize_server_call(server_call_id).resume_recording(server_call_id,
                                                                                                recording_id)

            Logger.log_message(Logger.INFORMATION,
                               "ResumeRecording response --> " + str(res))
            return web.Response(text="Ok")
        except Exception as ex:
            Logger.log_message(
                Logger.ERROR, "Failed to resume server recording --> " + str(ex))
            if CALL_RECODING_NOT_FOUND_ERROR_CODE in str(ex):
                return web.Response(text=str(ex), status=400)
            return web.Response(text=str(ex), status=500)

    async def stop_recording(request):
        try:
            server_call_id = request.rel_url.query['serverCallId']
            recording_id = request.rel_url.query['recordingId']

            Logger.log_message(
                Logger.INFORMATION,
                'StopRecording called with serverCallId --> ' + server_call_id + ' and recordingId --> ' + recording_id)

            if not server_call_id:
                return web.Response(text="serverCallId is invalid", status=400)

            if not recording_id:
                recording_id = recording_data[server_call_id]
                if not recording_id:
                    return web.Response(text="recordingId is invalid", status=400)
            elif server_call_id not in recording_data.keys():
                recording_data[server_call_id] = recording_id

            res = calling_server_client.initialize_server_call(server_call_id).stop_recording(server_call_id,
                                                                                              recording_id)

            Logger.log_message(Logger.INFORMATION,
                               "StopRecording response --> " + str(res))
            return web.Response(text="Ok")
        except Exception as ex:
            Logger.log_message(
                Logger.ERROR, "Failed to stop server recording --> " + str(ex))
            if CALL_RECODING_NOT_FOUND_ERROR_CODE in str(ex):
                return web.Response(text=str(ex), status=400)
            return web.Response(text=str(ex), status=500)

    async def get_recording_state(request):
        try:
            server_call_id = request.rel_url.query['serverCallId']
            recording_id = request.rel_url.query['recordingId']

            Logger.log_message(Logger.INFORMATION,
                               'GetRecordingState called with serverCallId --> ' + server_call_id + 'and recordingId --> ' + recording_id)

            if not server_call_id:
                return web.Response(text="serverCallId is invalid", status=400)
            if not recording_id:
                return web.Response(text="recordingId is invalid", status=400)

            res = calling_server_client.initialize_server_call(server_call_id).get_recording_status(server_call_id,
                                                                                                    recording_id)

            Logger.log_message(Logger.INFORMATION,
                               "GetRecordingState response --> " + str(res))
            return web.Response(text=res.recording_state, status=200)
        except Exception as ex:
            Logger.log_message(
                Logger.ERROR, "Failed to get recording status --> " + str(ex))
            if CALL_RECODING_NOT_FOUND_ERROR_CODE in str(ex):
                return web.Response(text=str(ex), status=400)
            return web.Response(text=str(ex), status=500)

    async def get_recording_file(request):
        content = await request.content.read()
        post_data = str(content.decode('UTF-8'))
        status = OperationStatus.SUCCESS

        if post_data:
            Logger.log_message(
                Logger.INFORMATION, 'getRecordingFile called with raw data --> ' + post_data)
            json_data = ast.literal_eval(json.dumps(post_data))
            event = EventGridEvent.from_dict(ast.literal_eval(json_data)[0])
            Logger.log_message(Logger.INFORMATION,
                               "Event type is  --> " + str(event.event_type))
            Logger.log_message(Logger.INFORMATION,
                               "Request data --> " + str(event.data))

            event_data = event.data
            try:
                if event.event_type == 'Microsoft.EventGrid.SubscriptionValidationEvent':
                    try:
                        subscription_validation_event: SubscriptionValidationEventData = event_data
                        code = subscription_validation_event['validationCode']
                        if code:
                            data = {"validationResponse": code}
                            Logger.log_message(Logger.INFORMATION,
                                               "Successfully Subscribed EventGrid.ValidationEvent --> " + str(data))
                            return web.Response(body=str(data), status=200)
                    except Exception as ex:
                        Logger.log_message(
                            Logger.ERROR, "Failed to Subscribe EventGrid.ValidationEvent --> " + str(ex))
                        return web.Response(text=str(ex), status=500)

                if event.event_type == 'Microsoft.Communication.RecordingFileStatusUpdated':
                    acs_recording_file_status_updated_event_data: AcsRecordingFileStatusUpdatedEventData = event_data
                    acs_recording_chunk_info_properties: AcsRecordingChunkInfoProperties = \
                        acs_recording_file_status_updated_event_data[
                            'recordingStorageInfo']['recordingChunks'][0]

                    Logger.log_message(
                        Logger.INFORMATION, "acsRecordingChunkInfoProperties response data --> " + str(acs_recording_chunk_info_properties))

                    document_id = acs_recording_chunk_info_properties['documentId']
                    content_location = acs_recording_chunk_info_properties['contentLocation']
                    metadata_location = acs_recording_chunk_info_properties['metadataLocation']

                    process_recording_response = CallRecordingController.process_file(
                        document_id,
                        content_location,
                        'mp4',
                        'recording')

                    if process_recording_response is True:
                        Logger.log_message(
                            Logger.INFORMATION, "Start processing metadata -- >")

                        process_metadata_response = CallRecordingController.process_file(
                            document_id,
                            metadata_location,
                            'json',
                            'metadata')

                        if process_metadata_response is True:
                            Logger.log_message(
                                Logger.INFORMATION, "Processing recording and metadata files completed successfully.")
                        else:
                            Logger.log_message(
                                Logger.INFORMATION, "Processing metadata file failed with message --> " + str(process_metadata_response))
                            status = OperationStatus.FAIL
                    else:
                        Logger.log_message(
                            Logger.INFORMATION, "Processing recording file failed with message --> " + str(process_recording_response))
                        status = OperationStatus.FAIL

            except Exception as ex:
                Logger.log_message(
                    Logger.ERROR, "Failed to get recording file --> " + str(ex))
                status = OperationStatus.FAIL
        else:
            Logger.log_message(Logger.INFORMATION, "Postdata is invalid")
            status = OperationStatus.FAIL

        if status == OperationStatus.FAIL:
            return web.Response(text="Get recording file action failed", status=500)

        return web.Response(text="Get recording file operation succeeded", status=200)

    def process_file(document_id: str, download_location: str, file_format: str, download_type: str):
        global upload_response
        Logger.log_message(Logger.INFORMATION, "Start downloading " +
                           download_type + " file. Download url --> " + download_location)

        try:
            download_response = calling_server_client.start_download(
                download_location)

            Logger.log_message(
                Logger.INFORMATION, "Uploading {0} file to blob".format(download_type))

            if download_response is not None:
                file_name = "{0}.{1}".format(document_id, file_format)
                with open(file_name, 'wb') as rec_file:
                    while True:
                        try:
                            chunk = download_response.__next__()
                            rec_file.write(chunk)
                        except Exception as ex:
                            rec_file.close()
                            break

                upload_response = BlobStorageHelper.upload_file_to_storage(
                    container_name=container_name,
                    blob_name=file_name,
                    blob_connection_string=blob_connection_string)

                if os.path.exists(file_name):
                    os.remove(file_name)

                if upload_response is True:
                    Logger.log_message(
                        Logger.INFORMATION, "File {0} upload to Azure successful".format(file_name))
                else:
                    Logger.log_message(Logger.INFORMATION,
                                       "Failed to upload ->" + upload_response)
                    return False

                blob_sas_url = BlobStorageHelper.get_blob_sas_uri(
                    account_name=blob_storage_account_name,
                    account_key=blob_storage_account_key,
                    container_name=container_name,
                    blob_name=file_name)
                Logger.log_message(Logger.INFORMATION,
                                   "blob_url = " + blob_sas_url)

            else:
                return False
        except Exception as ex:
            Logger.log_message(Logger.ERROR, str(ex))
            if ex and ex.response and ex.response.request:
                Logger.log_message(Logger.INFORMATION,
                                   "exception request header ----> " + str(ex.response.request.headers))
                Logger.log_message(
                    Logger.INFORMATION, "exception response header ----> " + str(ex.response.headers))
                return str(ex)

        return True

    def startup(request):
        return web.Response(text="App is running.....")

    async def get_blob_sas_uri(request):
        blob_name = request.rel_url.query['blob_name']
        blob_sas_token = BlobStorageHelper.get_blob_sas_token(
            account_name=blob_storage_account_name,
            account_key=blob_storage_account_key,
            container_name=container_name,
            blob_name=blob_name)

        if blob_sas_token:
            blob_uri_template = 'https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{blob_sas_token}'
            blob_sas_url = blob_uri_template.format(
                account_name=blob_storage_account_name,
                container_name=container_name,
                blob_name=blob_name,
                blob_sas_token=blob_sas_token
            )
            return web.Response(text=blob_sas_url, status=200)
        return web.Response(text="Error occoured in getting blob sas uri")
