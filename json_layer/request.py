#!/usr/bin/env python

import copy

from json_base import json_base
from generator_parameters import generator_parameters
from comment import comment
from approval import approval
from sequence import sequence
from submission_details import submission_details

class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
            request.logger.error('Duplicate Approval Step: Request has already been %s approved' % (self.__approval))
        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    def __init__(self, author_name,  author_cmsid=-1,  author_inst_code='',  author_project='', json_input={}):

        self._json_base__schema = {
            '_id':'', 
            'prepid':'',
            'history':[],  
            'priority':'',
            'status':'',
            'completion_date':'', 
            'cmssw_release':'',
            'input_filename':'',
            'pwg':'',
            'validation':'',
            'dataset_name':'',
            'pileup_dataset_name':'',
            'www':'',
            'process_string':'',
            'input_block':'',
            'block_black_list':[], 
            'block_white_list':[], 
            'cvs_tag':'',
            'pvt_flag':'',
            'pvt_comment':'',
            'mcdb_id':'',
            'notes':'',
            'description':'',
            'remarks':'',
            'completed_events':-1,
            'total_events':-1,
            'member_of_chain':[],
            'member_of_campaign':'',
            'time_event':-1,
            'size_event':-1,
            'nameorfragment':'', 
            'version':0,
            'status':[],
            'type':'',
            'generators':'',
            'comments':[],
            'sequences':[],
            'generator_parameters':[], 
            'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project), 
            'reqmgr_name':[], # list of tuples (req_name, valid)
            'approvals':[],
            'update_details':[] }
            
        # update self according to json_input
        self.__update(json_input)
        self.__validate()
        
        # detect approval steps
        if self.get_attribute('mcdb_id') != -1:
            self._json_base__approvalsteps = ['approve', 'submit']
            
        
        # AFS submit directory
        self.submit_directory = '/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/'

    def __validate(self):
        if not self._json_base__json:
            return 
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)
    
    # for all parameters in json_input store their values 
    # in self._json_base__json
    def __update(self,  json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']
                    
    def add_comment(author_name, comment, author_cmsid=-1, author_inst_code='', author_project=''):
        comments = self.get_attribute('comments')
        new_comment = comment(author_name,  author_cmsid,  author_inst_code,  author_project).build(comment)
        comments.append(new_comment)
        self.set_attribute('comments',  comments)
    
    def add_sequence(self,
              steps=[],
              nameorfragment='',
              conditions='',
              eventcontent=[],
              datatier=[],
              beamspot='',
              customise=[],
              filtername='',
              geometry='',
              magField='',
              pileup='NoPileUp',
              datamix='NODATAMIXER',
              scenario='',
              processName='',
              harvesting='',
              particle_table='',
              inputCommands='',
              dropDescendant=False,
              donotDropOnInput=True,
              restoreRNDSeeds='',
              slhc=''):
        seq = sequence()
        seq.build(steps, nameorfragment, conditions, eventcontent, datatier, beamspot, customise, filtername, geometry, magField, pileup, datamix, scenario, processName, harvesting, particle_table, inputCommands, dropDescendant, donotDropOnInput, restoreRNDSeeds, slhc)
        sequences = self.get_attribute('sequences')
        index = len(sequences) + 1
        seq.set_attribute('index', index)
        sequences.append(seq.json())
        self.set_attribute('sequences', sequences)
   
    def build_cmsDriver(self, sequenceindex):
      command = 'cmsDriver.py %s' % (self.get_attribute('nameorfragment').decode('utf-8'))
      try:
          seq = sequence(self.get_attribute('sequences')[sequenceindex])
      except Exception:
          self.logger.error('Request %s has less sequences than expected. Missing step: %d' % (self.get_attribute('prepid'), sequenceindex), level='critical')
          return '' 
      
      return '%s %s' % (command, seq.build_cmsDriver())

    def build_cmsDrivers(self):
      commands = []
      for i in range(len(self.get_attribute('sequences'))):
        cd = self.build_cmsDriver(i)
        if cd:
            commands.append(cd)
      return commands  

    def approve(self,  index=-1):
        approvals = self.get_attribute('approvals')
        app = approval('')
        app.set_approval_steps(self._json_base__approvalsteps)
        
        # if no index is specified, just go one step further
        if index==-1:
            index = len(approvals)

        self.logger.log('Approving request %s for step "%s"' % (self.get_attribute('_id'), index))
        
        try:
            new_apps = app.approve(index)
            self.set_attribute('approvals',  new_apps)
            return True
        except app.IllegalApprovalStep as ex:
            return False
    
    def add_status(self,  index=-1):
        # if no index is specified, just go one step further
        if index==-1:
            status = self.get_attribute('status')
            if not status:
                index = 0 
            elif status in self._json_base__status:
                index = self._json_base__status.index(status)+1
            else:
		index = 0

        self.logger.log('Updating the status for request %s...' % (self.get_attribute('_id')))

        if index >= len(self._json_base__status):
            self.logger.error('Illegal Status index: %s' % (index))
            return False

        self.set_attribute('status',  self._json_base__status[index])
        return True
        
    
    def update_generator_parameters(self, generator_parameters={}):
        if not generator_parameters:
            return
        gens = self.get_attribute('generator_parameters')
        generator_parameters['version']=len(gens)+1
        self.set_attribute('generator_parameters',  gens.append(generator_parameters))
