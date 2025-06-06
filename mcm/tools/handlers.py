import time
import traceback
import logging
import random

from random import randint
from threading import Thread, Lock
from queue import Queue

from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.locker import locker, semaphore_events
import tools.settings as settings
from couchdb_layer.mcm_database import database
from tools.communicator import communicator
from json_layer.request import request, AFSPermissionError
from json_layer.chained_request import chained_request
from json_layer.batch import batch
from rest_api.BatchPrepId import BatchPrepId
from tools.logger import InjectionLogAdapter


# SETTING THREAD POOL###
class Worker(Thread):
    """Thread executing tasks from a given queue"""
    def __init__(self, tasks, name):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.worker_name = name
        self.logger = logging.getLogger("mcm_error")
        self.start()

    def run(self):
        while True:
            self.logger.info("Worker %s trying to get work" % (self.worker_name))
            func, args, kargs = self.tasks.get()
            try:
                self.logger.info("Worker %s acquired task: %s" % (self.worker_name, func))
                func(*args, **kargs)
            except Exception as e:
                self.logger.error("Exception in '%s' thread: %s Traceback:\n%s" % (
                    self.worker_name, str(e), traceback.format_exc()))

            finally:
                self.tasks.task_done()  # do we want to mark task_done if it crashed?


class ThreadPool:
    """Pool of threads consuming tasks from a queue"""
    def __init__(self, name, max_workers):
        self.tasks = Queue(0)
        self.name = name
        self.worker_number = max_workers
        self.logger = logging.getLogger("mcm_error")
        worker_name_pool = ["Antanas", "Adrian", "Giovanni", "Gaelle", "Phat"]

        for i in range(self.worker_number):  # number should be taken from DB
            _name = "%s-%s" % (worker_name_pool[randint(0, 4)], i)
            Worker(self.tasks, _name)  # number of concurrent worker threads

    def add_task(self, func, *args, **kargs):
        """Add a task to the queue"""
        self.logger.info("Adding a task: %s to the Queue %s. Currently in Queue: %s" % (
                func, id(self.tasks), self.get_queue_length()))

        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        self.tasks.join()

    def get_queue_length(self):
        """Return the number of tasks waiting in the Queue"""
        return self.tasks.qsize()

# END OF THREAD POOL

submit_pool = ThreadPool("submission", settings.get_value('threads_num_submission'))


class Handler():
    """
    A class which manages locks for the resources.
    """
    logger = logging.getLogger("mcm_error")
    hname = ''  # handler's name
    lock = None

    def __init__(self, **kwargs):
        self.prepid = kwargs['prepid']
        if 'lock' not in kwargs:
            self.lock = locker.lock(self.prepid)
        else:
            self.lock = kwargs['lock']


class ConfigMakerAndUploader(Handler):
    """
    Class preparing and uploading (if needed) the configuration
    and adding it for the given request
    """

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.check_approval = kwargs.get('check_approval', True)
        self.inject_logger = InjectionLogAdapter(logging.getLogger('mcm_inject'), {'handle': self.prepid})

    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            self.inject_logger.error('Could not acquire lock for ConfigMakerAndUploader. prepid %s' % (self.prepid))
            return False

        try:
            self.inject_logger.info('Acquired lock for ConfigMakerAndUploader. prepid %s' % (self.prepid))
            request_db = database('requests')
            req = request(request_db.get(self.prepid))
            ret = req.prepare_and_upload_config()
            self.inject_logger.info('Prepared and uploaded config: %s. prepid %s' % (ret, self.prepid))
            return True if ret else False

        finally:
            self.inject_logger.info('Releasing a lock for ConfigMakerAndUploader. prepid %s' % (self.prepid))
            self.lock.release()


class SubmissionsBase(Handler):

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.request_db = database('requests')
        self.inject_logger = InjectionLogAdapter(logging.getLogger('mcm_inject'), {'handle': self.prepid})
        self.queue_lock = kwargs.get('queue_lock', None)  # Lock if request is put in processing pool
        self.check_approval = kwargs.get('check_approval', True)
        self.database_name = None

    def submit_configs(self):
        # Upload all config files to config cache, with "configuration economy" already implemented
        for req_i, req in enumerate(self.requests):
            if (self.check_approval and req.get_attribute('approval') != 'approve') or req.get_attribute('status') != 'approved':
                message = 'Request %s is in "%s"/"%s" approval/status, requires "approve"/"approved"' % (
                    self.prepid,
                    req.get_attribute('approval'),
                    req.get_attribute('status'))
                self.inject_logger.error(message)
                return False

            req.check_for_collisions()
            if req_i == 0:
                req.get_input_dataset_status()
            req.set_attribute('approval', 'submit')
            req.reload()
            self.inject_logger.info('Set %s to %s/%s' % (self.prepid,
                                                         req.get_attribute('approval'),
                                                         req.get_attribute('status')))
            request_prepid = req.get_attribute('prepid')
            uploader = ConfigMakerAndUploader(prepid=request_prepid)
            if not uploader.internal_run():
                return False

        return True

    def inject_configs(self):
        # if not self.lock.acquire(blocking=False):
        #     self.inject_logger.error('Could not acquire lock for injection with prepid %s' % (self.prepid))
        #     return False

        l_type = locator()
        self.inject_logger.info('Injection with prepid %s' % (self.prepid))
        try:
            mcm_r = self.requests[-1]
            self.batch_name = BatchPrepId().next_batch_id(self.batch_name, create_batch=True)
            if self.batch_name:
                semaphore_events.increment(self.batch_name)

            self.inject_logger.info('Got batch name %s for prepid %s' % (self.batch_name, self.prepid))
            with ssh_executor(server=l_type.mcm_executor_node()) as ssh:
                cmd = self.make_injection_command(mcm_r)
                self.inject_logger.info('Command used for injecting requests %s: %s' % (self.prepid, cmd))
                # modify here to have the command to be executed
                _, stdout, stderr = ssh.execute(cmd)
                output = stdout.read().decode(encoding="utf-8")
                error = stderr.read().decode(encoding="utf-8")
                if error:
                    self.inject_logger.error('Error while injecting %s. %s' % (self.prepid, error))
                    if '.bashrc: Permission denied' in error:
                        raise AFSPermissionError(error)

                if output:
                    self.inject_logger.info('Output for %s injection. %s' % (self.prepid, output))

                if error and not output:  # money on the table that it will break as well?
                    self.notify('Request injection failed for %s' % (self.prepid),
                                'Error in wmcontrol: %s' % (error),
                                self.requests)
                    return False

                output_lines = output.split('\n')
                injected_workflows = [line.split()[-1] for line in output_lines if line.startswith('Injected workflow:')]
                if not injected_workflows:
                    # No workflows were created
                    self.notify('Request injection happened but no request manager names for %s' % (self.prepid),
                                'Injection has succeeded but no request manager names were registered. ' +
                                'Check with administrators.\nOutput:\n%s\n\nError:\n%s' % (output, error),
                                self.requests)
                    return False
                else:
                    self.inject_logger.info('Injected workflows: %s' % (injected_workflows))

                # what gets printed into the batch object
                added_request_managers = []
                once = set()
                for mcm_r in self.requests:
                    if mcm_r.get_attribute('prepid') in once:
                        continue

                    once.add(mcm_r.get_attribute('prepid'))
                    added = [{'name': workflow,
                              'content': {'pdmv_prep_id': mcm_r.get_attribute('prepid')}} for workflow in injected_workflows]
                    added_request_managers.extend(added)

                # edit the batch object
                with locker.lock(self.batch_name):
                    bdb = database('batches')
                    bat = batch(bdb.get(self.batch_name))
                    bat.add_requests(added_request_managers)
                    bat.update_history({'action': 'updated', 'step': self.task_name})
                    if not bat.reload():
                        self.inject_logger.error('Error saving %s' % (self.batch_name))
                        return False

                # reload the content of all requests as they might have changed already
                added_request_managers = [{'name': workflow,
                                           'content': {'pdmv_prep_id': self.task_name}} for workflow in injected_workflows]
                return self.injection_succeeded(added_request_managers)

        except AFSPermissionError as ape:
            raise ape
        except Exception:
            self.inject_logger.error("Error with injecting chains for %s :\n%s" % (self.prepid, traceback.format_exc()))
        finally:  # we decrement batch id and release lock on prepid+lower semaphore
            if self.batch_name:  # ditry thing for now. Because batch name can be None for certain use-cases in code above
                semaphore_events.decrement(self.batch_name)

    def internal_run(self):
        with locker.lock('%s-wait-for-approval' % (self.prepid)):
            self.inject_logger.info('Request injection: %s' % (self.prepid))
            self.inject_logger.info('Will acquire lock for RequestInjector. prepid %s' % (self.prepid))
            if not self.lock.acquire(blocking=False):
                message = 'The request with name %s is being handled already' % (self.prepid)
                self.inject_logger.error(message)
                return {
                    'prepid': self.prepid,
                    'results': False,
                    'message': message}

            try:
                self.requests, self.batch_name, self.task_name = self.get_requests_batch_type()
                if not self.submit_configs():
                    message = 'Problem with uploading the configuration for %s' % (self.prepid)
                    self.inject_logger.error(message)
                    return {
                        "prepid": self.prepid,
                        "results": False,
                        "message": message}
                else:
                    self.inject_logger.info('Configs uploaded successfully for %s' % (self.prepid))

                if not self.inject_configs():
                    message = 'Problem with injecting %s' % (self.prepid)
                    self.inject_logger.error(message)
                    return {
                        "prepid": self.prepid,
                        "results": False,
                        "message": message}
                else:
                    self.inject_logger.info('Injected successfully for %s' % (self.prepid))

                self.inject_logger.info('Successfully uploaded config and injected %s' % (self.prepid))
            except AFSPermissionError:
                self.inject_logger.error('Got AFS permission error')
                for req in self.requests:
                    if req.get_attribute('approval') == 'submit' and req.get_attribute('status') == 'approved':
                        self.inject_logger.info('Setting %s to approve/approved' % (req.get_attribute('prepid')))
                        req.reload(save_current=False)
                        req.update_history({'action': 'inject', 'step': 'Injection failed (AFS). Setting to approve/approved'})
                        req.set_attribute('approval', 'approve')
                        req.reload()
                    else:
                        self.inject_logger.info('Not soft resetting %s, because it is %s-%s' % (req.get_attribute('prepid'),
                                                                                                req.get_attribute('approval'),
                                                                                                req.get_attribute('status')))

            finally:
                self.logger.info('Finally releasing lock for %s %s' % (self.prepid, self.lock))
                self.lock.release()
                self.logger.info('After release %s %s' % (self.prepid, self.lock))
                if self.queue_lock:
                    self.queue_lock.release()

    def make_injection_command(self, mcm_r=None):
        locator_type = locator()
        directory = locator_type.workLocation()
        wmcontrol_path = locator_type.get_wmcontrol_path()
        prepid = mcm_r.get_attribute('prepid')
        proxy_file_name = '%s%s_voms_proxy.txt' % (directory, prepid)
        executable_file_name = '%sinjection_script_%s.sh' % (directory, mcm_r.get_attribute('prepid'))
        release_for_latest_python = settings.get_value('release_for_latest_python') or 'el9:x86_64'
        
        # Configuration for the `wmcontrol` instruction
        test_params = ''
        if locator_type.isDev():
            test_params = '--wmtest --wmtesturl cmsweb-testbed.cern.ch'

        # Create the injection script
        bash_file = [
            '#!/bin/bash',
            '',
            '# Binds for singularity containers',
            '# Mount /afs, /eos, /cvmfs, /etc/grid-security for xrootd',
            "export APPTAINER_BINDPATH='/afs,/cvmfs,/cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security,/eos,/etc/pki/ca-trust,/run/user,/var/run/user'",
            '',
            '#############################################################',
            '#         This script is used by McM when it performs       #',
            '#              the request injection to ReqMgr2             #',
            '#                                                           #',
            '#      !!! THIS FILE IS NOT MEANT TO BE RUN BY YOU !!!      #',
            '# If you want to run validation script yourself you need to #',
            '#     get a "Get test" script which can be retrieved by     #',
            '#  clicking a button next to one you just clicked. It will  #',
            '# say "Get test command" when you hover your mouse over it  #',
            '#      If you try to run this, you will have a bad time     #',
            '#############################################################',
            ''
        ]

        # Request a VOMS proxy certificate
        bash_file += [
            'cd %s' % (directory),
            '',
            '# Make a VOMS proxy certificate',
            'voms-proxy-init --voms cms --out %s --hours 4' % (proxy_file_name),
            'export X509_USER_PROXY=%s' % (proxy_file_name),
            '',
        ]

        # Create the injection script to execute `wmcontrol`
        bash_file += [
            'cat <<\'EndOfInjectFile\' > %s' % (executable_file_name),
            '#!/bin/bash',
            '',
            'cd %s' % (directory),
            'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh',
            'export PATH=%s:${PATH}' % (wmcontrol_path),
            'python3 `which wmcontrol.py` --dont_approve --url-dict %spublic/restapi/%s/get_dict/%s %s' % (
                locator_type.baseurl(), self.database_name, self.prepid, test_params
            ),
            '',
            '# End of injection script',
            'EndOfInjectFile',
            '',
        ]

        # Execution using singularity
        bash_file += [
            'chmod +x %s' % (executable_file_name),
            '# Run in singularity container',
            'singularity run --home $PWD:$PWD /cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/%s %s' % (release_for_latest_python, executable_file_name),
            '',
            'rm -f %s' % (executable_file_name),
            'rm -f %s' % (proxy_file_name),
            '',
        ]

        command = '\n'.join(bash_file)
        self.logger.info('Inject command:\n\n%s\n\n' % (command))
        return command

    def notify(self, subject, message, req):
        self.inject_logger.info('Notify:\n  Subject: %s\n\n  Message: %s' % (subject, message))
        if not isinstance(req, list):
            req = [req]

        recipients = []
        for r in req:
            recipients.extend(r.get_actors(what='author_email'))

        recipients = sorted(list(set(recipients)))
        req = req[-1]
        if req is not None:
            req.notify(subject, message, who=recipients)
        else:
            self.logger.error('Could not notify because request object is None. Subject: %s' % (subject))

    def injection_succeeded(self, added_requests):
        raise NotImplementedError()

    def get_requests_batch_type(self):
        '''
        Return a list of requests, batch name and task type
        '''
        raise NotImplementedError()


class RequestInjector(SubmissionsBase):
    def __init__(self, **kwargs):
        SubmissionsBase.__init__(self, **kwargs)
        self.database_name = 'requests'

    def get_requests_batch_type(self):
        '''
        Return a list of requests, batch name and task type
        '''
        self.req = request(self.request_db.get(self.prepid))
        return [self.req], self.req.get_attribute('member_of_campaign'), self.prepid

    def injection_succeeded(self, added_request_managers):
        self.req.reload(save_current=False)
        request_managers = self.req.get_attribute('reqmgr_name')
        request_managers.extend(added_request_managers)
        self.req.set_attribute('reqmgr_name', request_managers)
        # and in the end update request in database
        self.req.update_history({'action': 'inject', 'step': self.batch_name})
        self.req.set_attribute('approval', 'submit')
        self.req.set_status(step=self.req._json_base__status.index('submitted'), with_notification=True)
        saved = self.request_db.update(self.req.json())
        if not saved:
            self.inject_logger.error('Could not update request %s in database' % (self.prepid))
            return False

        subject = 'Injection succeeded for %s' % self.requests[-1].get_attribute('prepid')
        self.notify(subject, self.req.textified(), self.req)
        for added_req in added_request_managers:
            self.inject_logger.info('Request %s added to %s' % (added_req['name'], self.batch_name))

        return True


class ChainRequestInjector(SubmissionsBase):
    def __init__(self, **kwargs):
        SubmissionsBase.__init__(self, **kwargs)
        self.chained_requests_db = database('chained_requests')
        self.database_name = 'chained_requests'

    def get_requests_batch_type(self):
        '''
        Return a list of requests, batch name and task type
        '''
        if not self.chained_requests_db.document_exists(self.prepid):
            # It's a request actually, pick up all chains containing it
            mcm_request = self.request_db.get(self.prepid)
            mcm_crs = self.chained_requests_db.query_view('contains', self.prepid, page_num=-1)
            task_name = 'task_' + self.prepid
        else:
            mcm_crs = [self.chained_requests_db.get(self.prepid)]
            current_step_prepid = mcm_crs[0]['chain'][mcm_crs[0]['step']]
            mcm_request = self.request_db.get(current_step_prepid)
            task_name = 'task_' + current_step_prepid

        batch_name = 'Task_' + mcm_request['member_of_campaign']
        # Filter only chained request ready to be used
        mcm_crs = [
            cr
            for cr in mcm_crs
            if cr.get('action_parameters').get('flag')
        ]

        if len(mcm_crs) == 0:
            return

        mcm_requests = []
        for cr in mcm_crs:
            mcm_cr = chained_request(cr)
            chain = mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]
            for request_prepid in chain:
                req = request(self.request_db.get(request_prepid))
                mcm_requests.append(req)

        self.mcm_crs = mcm_crs
        return mcm_requests, batch_name, task_name

    def injection_succeeded(self, added_request_managers):
        seen = set()
        for cr in self.mcm_crs:
            mcm_cr = chained_request(cr)
            chain = mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]
            message = 'Following requests in %s chain were injected:\n\n' % (cr.get('prepid', '* no-prepid *'))
            reqs = []
            for rn in chain:
                if rn in seen:
                    continue  # don't do it twice

                seen.add(rn)
                mcm_r = request(self.request_db.get(rn))
                message += mcm_r.textified()
                message += "\n\n"
                mcm_r.set_attribute('reqmgr_name', added_request_managers)
                mcm_r.update_history({'action': 'inject', 'step': self.batch_name})
                # if not self.check_approval:
                #     mcm_r.set_attribute('approval', 'submit')
                # set the status to submitted
                mcm_r.set_attribute('approval', 'submit')
                mcm_r.set_status(step=mcm_r._json_base__status.index('submitted'), with_notification=False)
                mcm_r.reload()
                mcm_cr.set_attribute('last_status', mcm_r.get_attribute('status'))
                reqs.append(mcm_r)

            # re-get the object
            mcm_cr = chained_request(self.chained_requests_db.get(cr['prepid']))
            # take care of changes to the chain
            mcm_cr.update_history({'action': 'inject', 'step': self.batch_name})
            mcm_cr.set_attribute('step', len(mcm_cr.get_attribute('chain')) - 1)
            mcm_cr.set_attribute('status', 'processing')
            subject = 'Injection succeeded for %s' % (cr.get('prepid', '* no-prepid *'))
            self.notify(subject, message, reqs)
            mcm_cr.reload()

        return True


class RequestApprover(Handler):
    def __init__(self, batch_id, workflows):
        self.workflows = workflows
        self.batch_id = batch_id

    def make_command(self):
        l_type = locator()
        wmcontrol_path = l_type.get_wmcontrol_path()
        proxy_file_name = './%032x_voms_proxy.txt' % (random.getrandbits(128))
        approve_script_name = './approve_%s_file.sh' % (self.batch_id)

        # Pick a release including latest Python features
        try:
            release_for_latest_python = settings.get_value('release_for_latest_python')
        except Exception as e:
            self.logger.error(
                "Unable to retrieve the Python release for singularity: %s", 
                e,
                exc_info=True
            )
            release_for_latest_python = 'el9:x86_64'

        # Script target
        test_params = ''
        if l_type.isDev():
            test_params = '--wmtest --wmtesturl cmsweb-testbed.cern.ch'

        # Create the approve script
        bash_file = [
            '#!/bin/bash',
            '',
            '# Binds for singularity containers',
            '# Mount /afs, /eos, /cvmfs, /etc/grid-security for xrootd',
            "export APPTAINER_BINDPATH='/afs,/cvmfs,/cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security,/eos,/etc/pki/ca-trust,/run/user,/var/run/user'",
            '',
            '#############################################################',
            '#        This script is used by McM to approve requests     #',
            '#            in ReqMgr2 after batch announcement.           #',
            '#        Setting the workflow to assignment-approved so     #',
            '#               computing starts processing it.             #',
            '#                                                           #',
            '#      !!! THIS FILE IS NOT MEANT TO BE RUN BY YOU !!!      #',
            '# If you want to run validation script yourself you need to #',
            '#     get a "Get test" script. Click on the button that     #',
            '# says "Get test command" when you hover your mouse over it #',
            '#      If you try to run this, you will have a bad time     #',
            '#############################################################',
            ''
        ]

        # Folder for storing the approve script and the proxy certificate
        bash_file += [
            '',
            'echo "Executing approve script at: $(hostname)"',
            '',
            "export APPROVE_FOLDER=$(mktemp -d -t 'McM_Approve_XXXXXXXXXX')",
            'echo "Approve folder available at: $APPROVE_FOLDER"',
            'cd $APPROVE_FOLDER/',
            'voms-proxy-init --voms cms --out %s --hours 1' % (proxy_file_name),
            ''
        ]

        # Create the injection script to execute `wmcontrol`
        bash_file += [
            'cat <<\'EndOfApproveFile\' > %s' % (approve_script_name),
            '#!/bin/bash',
            '',
            'export X509_USER_PROXY=%s' % (proxy_file_name),
            'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh',
            'export PATH=%s:${PATH}' % (wmcontrol_path),
            'python3 `which wmapprove.py` --workflows %s %s' % (self.workflows, test_params),
            '',
            '# End of approve script',
            'EndOfApproveFile',
            ''
        ]

        # Execution using singularity
        bash_file += [
            'chmod +x %s' % (approve_script_name),
            '# Run in singularity container',
            'singularity run --home $PWD:$PWD /cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/%s %s' % (release_for_latest_python, approve_script_name),
            '',
            '# Remove the temporary folder',
            'rm -rf "$APPROVE_FOLDER"',
            ''
        ]

        command = '\n'.join(bash_file)
        self.logger.info('Approve command:\n\n%s\n\n' % (command))
        return command

    def send_email_failure(self, output, error):
        com = communicator()
        users_db = database('users')
        production_managers = users_db.search({'role': 'production_manager'}, page=-1)
        subject = "There was an error while trying to approve workflows"
        text = "Workflows: %s\nOutput:\n%s\nError output: \n%s" % (self.workflows, output, error)
        com.sendMail(
            [u['email'] for u in production_managers],
            subject,
            text)

    def internal_run(self):
        l_type = locator()
        command = self.make_command()
        try:
            trails = 1
            while trails < 3:
                self.logger.info("Wmapprove trail number: %s" % trails)
                with ssh_executor(server=l_type.mcm_executor_node()) as executor:
                    _, stdout, stderr = executor.execute(command)
                    if not stdout and not stderr:
                        self.logger.error('ssh error for request approvals, batch id: ' + self.batch_id)
                        return

                    output = stdout.read().decode(encoding="utf-8")
                    error = stderr.read().decode(encoding="utf-8")

                self.logger.info('Wmapprove output: %s' % output)
                if not error and 'Something went wrong' not in output:
                    break
                time.sleep(3)
                trails += 1
            if error or 'Something went wrong' in output:
                message = 'Error in wmapprove: %s' % (output if 'Something went wrong' in output else error)
                self.logger.error(message)
                self.send_email_failure(output, error)
                return {
                    'results': False,
                    'message': message}
        except Exception as e:
            message = 'Error while approving requests, batch id: %s, message: %s' % (self.batch_id, str(e))
            self.logger.error(message, exc_info=True)
            self.send_email_failure('', message)
            return {
                'results': False,
                'message': message}
        return {'results': True}
