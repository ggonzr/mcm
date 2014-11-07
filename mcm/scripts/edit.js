
var ModalDemoCtrl = function ($scope, $modal) {
  $scope.openSequenceEdit = function (seq1, seq2, number) {
    $scope.sequenceToShow = [];
    $scope.sequenceHidden = [];
    var sequences = {};
    _.each($scope.dbName == "requests" ? $scope.result.sequences[number] : $scope.result.sequences[seq1][seq2], function(value,key){
        if (! _.isEmpty(value) || _.isBoolean(value) || _.isNumber(value)) {
          $scope.sequenceToShow.push(key);
        } else {
          $scope.sequenceHidden.push(key);
        }
        sequences[key]=value;
    });
    //sort both lists ???
    $scope.sequenceHidden.sort();
      var sequenceEditModal = $modal.open({
          templateUrl: 'sequenceEditModal.html',
          controller: SequenceEditModalInstanceCtrl,
          resolve: {
              sequenceHidden: function() {
                  return $scope.sequenceHidden;
              },
              sequenceToShow: function() {
                  return $scope.sequenceToShow;
              },
              selectedHidden: function() {
                  return $scope.sequenceHidden[0];
              },
              sequences: function() {
                  return sequences;
              }
          }
      });
      sequenceEditModal.result.then(function(newSequence) {
         if( $scope.dbName == "requests") {
            $scope.result.sequences[number] = newSequence; // we should somehow change driver shown as well
         } else {
            $scope.result.sequences[seq1][seq2] = newSequence;
         }
      });
  };

  $scope.openNewSequence = function(define_name, index) {
      var sequenceAddModal = $modal.open({
          templateUrl: 'sequenceAddModal.html',
          controller: SequenceAddModalInstanceCtrl,
          resolve: {
              define_name: function() {
                  return define_name;
              },
              defaultSequence: function() {
                  return _.clone($scope.default_sequences);
              }
          }
        });
      sequenceAddModal.result.then(function(data) {
          if($scope.dbName == "requests") {
              $scope.drivers.push(data.sequence);
              $scope.result.sequences.push(data.sequence);
          } else {
              if(!define_name) {
                $scope.drivers[_.size($scope.result.sequences)] = {default: data.sequence};
                $scope.result.sequences[_.size($scope.result.sequences)] = {default: data.sequence};
              } else {
                $scope.drivers[index][data.name] = data.sequence;
                $scope.result.sequences[index][data.name] = data.sequence;
              }
          }
      })
  };

  $scope.isBoolean = function(value){
    return angular.isBoolean(value);
  };

};


var SequenceAddModalInstanceCtrl = function($scope, $modalInstance, define_name, defaultSequence) {
    $scope.define_name = define_name;
    $scope.sequences = {
        newSequenceName: "",
        newSequence: defaultSequence
    };

    $scope.save = function() {
        $modalInstance.close({name: $scope.sequences.newSequenceName, sequence: $scope.sequences.newSequence});
    };

    $scope.close = function() {
        $modalInstance.dismiss();
    }
};

var SequenceEditModalInstanceCtrl = function($scope, $modalInstance, sequences, selectedHidden, sequenceToShow, sequenceHidden) {
    $scope.sequence = {
        toShow: sequenceToShow,
        hidden: sequenceHidden,
        selectedHidden: selectedHidden,
        sequences: sequences
    };

    $scope.showHiddenSequence = function() {
        $scope.sequence.toShow.push($scope.sequence.selectedHidden);
        $scope.sequence.hidden.splice($scope.sequence.hidden.indexOf($scope.sequence.selectedHidden), 1);
        $scope.sequence.selectedHidden = $scope.sequence.hidden[0];
    };
    $scope.close = function() {
        $modalInstance.dismiss();
    };
    $scope.save = function() {
        $modalInstance.close($scope.sequence.sequences);
    }
};

var genParamModalCtrl = function($scope, $http, $modal) {

  $scope.showData = {
      "Cross section": "cross_section",
      "Filter efficiency": "filter_efficiency",
      "Filter efficiency error": "filter_efficiency_error",
      "Match efficiency": "match_efficiency",
      "Match efficiency error": "match_efficiency_error"
  };

  $scope.openGenParam = function(action, index) {
      var data = [];
      if(action == "Edit") {
          data = $scope.genParam_data[index];
      } else {
          data = $scope.defaultGenParams;
      }
    var genParamModal = $modal.open({
      templateUrl: 'generatorParamsModal.html',
      controller: GeneratorParamsInstandeModal,
      resolve: {
          data: function() {
              return _.clone(data);
          },
          action: function() {
              return action;
          },
          showData: function() {
              return $scope.showData;
          }
      }
    });
    genParamModal.result.then(function(new_gen_params) {
        _.each(new_gen_params, function(elem,key){
          if (_.isString(elem) && key !="$$hashKey"){
            new_gen_params[key] = parseFloat(elem);
          }
        });
        if(action == "Edit") {
            _.each(new_gen_params, function(elem,key){
              if (!isNaN(elem)){
                $scope.genParam_data[index][key] = elem;
              }
            });
        } else { // Add
            $scope.genParam_data.push(new_gen_params);
        }
    });

  };

};

var GeneratorParamsInstandeModal = function($scope, $modalInstance, data, action, showData) {
    $scope.action = action;
    $scope.gen_params = {
        data: data,
        show: showData
    };
    $scope.closeGenParam = function() {
        $modalInstance.dismiss();
    };

    $scope.saveGenParam = function() {
        $modalInstance.close($scope.gen_params.data);
    };
};

testApp.directive("sequenceEdit", function($http){
  return {
    require: 'ngModel',
    template:
    '<div >'+
    '  <script type="text/ng-template" id="sequenceEditModal.html">'+ // Edit sequence modal template
    '     <div class="modal-header">'+
    '       <h4>Edit sequence</h4>'+
    '     </div>'+
    '     <div class="modal-body">'+
    '       <form class="form-horizontal" name="sequenceForm">'+
    '         <div class="control-group" ng-repeat="key in sequence.toShow">'+
    '          <div ng-if="key!=$$hashkey">'+
    '           <label class="control-label">{{key}}</label>'+
    '             <input type="text" ng-model="sequence.sequences[key]">'+
    '          </div>' +
    '         </div>'+
    '       </form>'+
    '     </div>'+
    '     <div class="modal-footer">'+
    '       <div class="span3 input-append" style="text-align:left;">'+
    '         <select ng-model="sequence.selectedHidden" ng-show="sequence.hidden.length > 0">'+
    '           <option ng-repeat="elem in sequence.hidden">{{elem}}</option>'+
    '         </select>'+
    '         <a class="btn" ng-click="showHiddenSequence();" ng-href="#" ng-show="sequence.hidden.length > 0"><i class="icon-plus-sign"></i></a>'+
    '       </div>'+
    '       <div class="span2">'+
    '         <button class="btn btn-success" ng-click="save()">Save</button>'+
    '         <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '       </div>'+
    '     </div>'+
    '  </script>'+
    '  <script type="text/ng-template" id="sequenceAddModal.html">'+ //Add sequence modal template
    '    <div class="modal-header">'+
    '      <h4>Add sequence</h4>'+
    '    </div>'+ //end oF  modal header
    '    <div class="modal-body">'+
    '      <form class="form-horizontal" name="sequenceForm">'+
    '        <div class="control-group" ng-if="define_name">'+
    '          <label class="control-label">Name</label>'+
    '          <div class="controls">'+
    '            <input type="text" ng-model="sequences.newSequenceName" name="Name" required>'+
    '            <span class="error" ng-show="sequenceForm.Name.$error.required">'+
    '               Required!</span>'+
    '          </div>'+
    '        </div>'+
    '        <div class="control-group" ng-repeat="(key, value) in sequences.newSequence">'+
    '          <div ng-if="key!=$$hashKey">'+
    '            <label class="control-label">{{key}}</label>'+
    '            <div class="controls">'+
    '              <input type="text" ng-model="sequences.newSequence[key]">'+
    '            </div>'+
    '          </div>'+
    '      </form>'+
    '    </div>'+ //end of modal body
    '    <div class="modal-footer">'+
    '      <button class="btn btn-success" ng-click="save()" ng-disabled="sequenceForm.Name.$error.required">Save</button>'+
    '      <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '    </div>'+ //end of modal footer
    '  </script>'+
    '  <ul ng-switch="dbName">'+
    '   <a rel="tooltip" title="Display sequences" ng-click="displaySequences();" ng-hide="showSequences" ng-href="#">'+
    '     <i class="icon-eye-open"></i>'+
    '   </a>'+
    '   <a rel="tooltip" title="Display sequences" ng-click="displaySequences();" ng-show="showSequences" ng-href="#">'+
    '     <i class="icon-eye-close"></i>'+
    '   </a>'+
    '  <div ng-switch-when="requests" ng-show="showSequences">'+
    '    <li ng-repeat="(sequence_id, sequence) in drivers">{{sequence}}'+
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <a rel="tooltip" title="Edit sequence" ng-click="openSequenceEdit(\'\',\'\',sequence_id);" ng-hide="hideSequence(1);" ng-href="#">'+
    '          <i class="icon-wrench"></i>'+
    '        </a>'+
    '        <a rel="tooltip" title="Remove sequence" ng-click="removeSequence($index);" ng-hide="hideSequence(1);" ng-href="#">'+
    '          <i class="icon-remove-sign"></i>'+
    '        </a>'+
    '    </li>'+
    '  </div>'+
    '  <div ng-switch-default ng-show="showSequences">'+
    '    <li ng-repeat="(key,value) in result.sequences">'+
    '      <ul>'+
    '        {{key}}'+
    '      </ul>'+
    '      <ul ng-repeat="(name,elem) in value">'+
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <li>{{drivers[key][name]}}'+
    '          <a rel="tooltip" title="Edit sequence" ng-click="openSequenceEdit(key,name,$index);" ng-hide="hideSequence(1);" ng-href="#">'+
    '            <i class="icon-wrench"></i>'+
    '          </a>'+
    '          <a rel="tooltip" title="Remove subsequence" ng-click="removeSubSequence(key, name);" ng-hide="hideSequence(1);" ng-href="#">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-remove-sign"></i>'+
    '          </a>'+
    '        </li>'+
    '      </div>'+ //end of modalControler DIV
    '      </ul>'+
    '        <div ng-controller="ModalDemoCtrl">'+
    '          <a rel="tooltip" title="Remove sequence" ng-click="removeSequence(key);" ng-hide="hideSequence(1);" ng-href="#">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-remove-sign"></i>'+
    '          </a>'+
    '          <a rel="tooltip" title="Add new subsequence" ng-click="openNewSequence(true, $index);" ng-hide="hideSequence(1);" ng-href="#">'+ //add sequence
    '            <i class="icon-plus"></i>'+
    '          </a>'+
    '        </div>'+
    '    </li>'+
    '  </div>'+
    '  </ul>'+
    '  <div ng-controller="ModalDemoCtrl" ng-show="showSequences">'+ //add new sequence to sequence list
    '    <a rel="tooltip" title="Add new sequence" ng-click="openNewSequence(false);" ng-hide="hideSequence(1);" ng-href="#">'+ //add sequence
    '      <i class="icon-plus"></i>'+
    '    </a>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.showSequences = false;
        scope.showAddNewModal = false;
        scope.default_sequences = {};
        scope.sequenceToShow = [];
        scope.sequenceHidden = [];
        scope.alreadyShown = false;
      };
      scope.removeSequence = function(elem){
        scope.result.sequences.splice(elem, 1); //remove the value from original sequences
        scope.drivers.splice(elem, 1);
      };
      scope.removeSubSequence = function(key, name){
        if (scope.result.sequences[key] != null){
          delete scope.result.sequences[key][name];
          delete scope.drivers[key][name];
        }
        if (_.keys(scope.result.sequences[key]).length == 1){ //$$hashkey dosent count
          scope.result.sequences.splice(key,1);
          scope.drivers.splice(key, 1);
        }
      };
      scope.displaySequences = function(){
        if (scope.showSequences){ //if shown then -> HIDE;
          scope.showSequences = false;
        } else {
          scope.showSequences = true; //if hidden -> then display sequences, get the cmsDrivers;
          if(!scope.alreadyShown) {
               var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.result.prepid);
                promise.then(function(data){
                    scope.drivers = data.data.results;

                }, function(data){
                    alert("Error: " + data.status);
                });
               var promise2 = $http.get("getDefaultSequences");
              promise2.then(function(data) {
                  scope.default_sequences = data.data;
              }, function() {
                  alert("Error getting default sequences");
              });
              scope.alreadyShown = true;
          }
        }
      };
    }
  }
});
testApp.directive("customHistory", function(){
  return {
    require: 'ngModel',
    template:
    '<div>'+
    '  <div ng-hide="show_history">'+
    '    <input type="button" value="Show" ng-click="show_history=true;">'+
    '  </div>'+
    '  <div ng-show="show_history">'+
    '    <input type="button" value="Hide" ng-click="show_history=false;">'+
    '    <table class="table table-bordered" style="margin-bottom: 0px;">'+
    '      <thead>'+
    '        <tr>'+
    '          <th style="padding: 0px;">Action</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '          <th style="padding: 0px;">Step</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
    '          <td style="padding: 0px;">{{elem.updater.submission_date}}</td>'+
    '          <td style="padding: 0px;">'+
    '              <div ng-switch="elem.updater.author_name">'+
    '                <div ng-switch-when="">{{elem.updater.author_username}}</div>'+
    '                <div ng-switch-default>{{elem.updater.author_name}}</div>'+
    '              </div>'+
    '          </td>'+
    '          <td style="padding: 0px;">{{elem.step}}</td>'+
    '        </tr>'+
    '      </tbody>'+
    '    </table>'+
    '  </div>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.show_history = false;
        scope.show_info = ctrl.$viewValue;
      };
    }
  }
});
testApp.directive("selectCampaign", function(){
  return{
      require: 'ngModel',
      template:
      '<div>'+
      '  <a ng-repeat="elem in allowedCampaigns" ng-click="removeAllowedCampaign(elem)">{{elem}}<i class="icon-minus"></i></a>'+ //display allowed campaign list with possibility to remove it
      '</div>'+
      '<a ng-click="displaySelect();" ng-hide="selectACampaign && all_campaigns.length ==1"><i class="icon-plus"></i></a>'+ //options to add a new campaign from available list
      '<select ng-change="allowCampaign();" ng-model="toAllow" ng-options="value for value in all_campaigns" ng-show="selectACampaign && all_campaigns.length !=1"></select>'
      ,
      link: function(scope, element, attr, ctrl){
        ctrl.$render = function () {
          scope.selected_column = attr.value;
          scope.allowedCampaigns = ctrl.$viewValue;
          scope.all_campaigns = _.difference(scope.allCampaigns, scope.allCampaigns);
          scope.all_campaigns.push("------");

        }
        scope.displaySelect = function(){
          var notAllowedlist = _.clone(scope.allowedCampaigns); //get a deepcopy of allowed campaigns
          notAllowedlist.push(scope.result['next_campaign']); // push next campaign so exlude list
          scope.all_campaigns = _.difference(scope.allCampaigns, notAllowedlist); //get only those that are not in allowed campaigns & next_campaign
          scope.all_campaigns.push("------");
          scope.toAllow = "------"; //by default preselected value
          scope.selectACampaign = true;
        };
        scope.allowCampaign = function(){
          scope.allowedCampaigns.push(scope.toAllow); //push a selected value
          scope.selectACampaign = false;
        }
        scope.removeAllowedCampaign = function(campaign_name){
          scope.allowedCampaigns = _.without(scope.allowedCampaigns, campaign_name);
          scope.result["allowed_campaigns"] = _.without(scope.allowedCampaigns, campaign_name);
          scope.all_campaigns.push(campaign_name);
          // scope.allowedCampaigns.push(campaign_name); //push a selected value
        }
      }
  }
});

testApp.directive("generatorParams", function($http){
  return {
    require: 'ngModel',
    template:
    '<div ng-controller="genParamModalCtrl">'+
        ///MODAL
    '  <script  type="text/ng-template" id="generatorParamsModal.html">'+ //hidden modal template
    '    <div class="modal-header">'+
    '      <h4>{{action}} generator parameters</h4>'+
    '    </div>'+ //end of modal header
    '    <div class="modal-body">'+
    '      <form class="form-horizontal">'+
    '        <div ng-repeat="(key, value) in gen_params.show" class="control-group">'+
    '          <label class="control-label">{{key}}</label>'+
    '          <div class="controls">'+
    '            <input type="text" ng-model="gen_params.data[value]">'+
    '            <a ng-if="key==\'Cross section\'" class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '          </div>'+
    '        </div>'+
    '      </form>'+
    '    </div>'+ //end of modal body
    '    <div class="modal-footer">'+
    '      <button class="btn btn-success" ng-click="saveGenParam()">Save</button>'+
    '      <button class="btn btn-warning cancel" ng-click="closeGenParam()">Cancel</button>'+
    '    </div>'+ //end of modal footer
    '  </script>'+///END OF MODAL
    '  <ul ng-repeat="elem in genParam_data">'+
    '    <li>'+ //when not the last element display only wrench
    '      <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;" ng-if="$index==genParam_data.length-1">'+
    '        <dt ng-repeat-start="(key, value) in showData">{{key.toLowerCase()}}</dt>'+
    '        <dd ng-repeat-end class="clearfix">{{elem[value]}}'+
    '          <a ng-if="key==\'Cross section\'" class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '        </dd>'+
    '        <dt>author username</dt>'+
    '        <dd class="clearfix">{{elem["submission_details"]["author_username"]}}</dd>'+
    '      </dl>'+
    '      <a ng-click="openGenParam(\'Edit\', $index)" ng-hide="not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-wrench"></i></a>'+
    '    </li>'+
    '  </ul>'+
    '      <a ng-click="openGenParam(\'Add\')" ng-hide="addParamLoad || not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-plus"></i></a>'+
    '      <img ng-show="addParamLoad" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.genParam_data = ctrl.$viewValue;
        scope.defaultGenParams = [];
      };

        scope.addParamLoad = true;
        var promise = $http.get("restapi/"+ scope.dbName+"/default_generator_params/"+scope.result["prepid"]);
        promise.then(function(data){
          scope.defaultGenParams = data.data.results;
            scope.addParamLoad = false;
        }, function(){
          alert("Error getting default generator parameters");
        });
    }
  }
});

testApp.directive("inlineEditable", function ($modal) {
    return {
        require: 'ngModel',
        template: '<textarea style="width:95%; height:150px" ng-model="whatever_value" ng-change="update()" ng-disabled="not_editable_list.indexOf(formColumn)!=-1"></textarea>',
        link: function (scope, element, attr, ctrl) {
            ctrl.$render = function () {
                scope.whatever_value = JSON.stringify(ctrl.$viewValue, null, 4);
                scope.formColumn = scope.$eval(attr.column);
            };
            scope.update = function () {
                var object = null;
                try {
                    object = JSON.parse(scope.whatever_value);
                    ctrl.$setViewValue(object);
                    ctrl.$setValidity("bad_json", true);
                } catch (err) {
                    ctrl.$setValidity("bad_json", false);
                }
            };
            scope.openRequestParametersModal = function () {
                $modal.open({
                    templateUrl: "HTML/templates/edit.request.parameters.html",
                    controller: EditRequestParametersCtrl,
                    resolve: {
                        initRequestParams: function () {
                            return JSON.parse(scope.whatever_value);
                        },
                        getCtrl: function () {
                            return ctrl;
                        },
                        getScope: function () {
                            return scope;
                        }
                    }
                });
            };
        }
    };
});

var EditRequestParametersCtrl = function ($scope, $modalInstance, initRequestParams, getCtrl, getScope) {
    $scope.data = [{name: "Time Event", value: initRequestParams.time_event, id: "time_event", type: "int"}, {name: "Size Event", value: initRequestParams.size_event, id: "size_event", type: "int"}, {name: "Process String", value: initRequestParams.process_string, id: "process_string"}, {name: "Sequences", value: initRequestParams.sequences, id: "sequences"}];
    $scope.done = function () {
        var newJSON = {};
        for (var i in $scope.data) {
            if ($scope.data[i].value) {
                if ($scope.data[i].type=='int') {
                    newJSON[$scope.data[i].id] = parseInt($scope.data[i].value, 10);
                } else {
                    newJSON[$scope.data[i].id] = $scope.data[i].value;
                }
            }
        }
        try {
            getScope.whatever_value = JSON.stringify(newJSON, undefined, 4);
            getCtrl.$setViewValue(newJSON);
            getCtrl.$setValidity("bad_json", true);
        } catch (err){
            getCtrl.$setValidity("bad_json", false);
        }
        $modalInstance.dismiss();
    };
    
    $scope.close = function() {
        $modalInstance.dismiss();
    }
};

testApp.directive("customValidationEdit", function(){
  return {
    require: 'ngModel',
    replace: true,
    restrict: 'E',
    template:
    '<div ng-switch on="dbName">'+
    '  <form ng-switch-when="requests">'+
    '    <fieldset>'+
    '      <div class="control-group">'+
    '        Valid:'+
    '        <input type="checkbox"  ng-model="validation_data.valid" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1">'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.valid">'+
    '        nEvents:'+
    '        <input type="number"  ng-model="validation_data.nEvents" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1">'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.dqm">'+
    '        DQM:'+
    '        <a ng-show="isDevMachine()" href="https://cmsweb-testbed.cern.ch/dqm/dev/start?runnr=1;dataset={{data[value.db_name].dqm}};workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for {{data[value.db_name].dqm}}" target="_blank">'+
    '          <i class="icon-th-large"></i>'+
    '        </a>'+
    '        <a ng-show="!isDevMachine()" href="https://cmsweb.cern.ch/dqm/dev/start?runnr=1;dataset={{data[value.db_name].dqm}};workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for {{data[value.db_name].dqm}}" target="_blank">'+
    '          <i class="icon-th-large"></i>'+
    '        </a>'+
    '      </div>'+
    '    </fieldset>'+
    '  </form>'+
    '  <input type="text" ng-switch-default ng-model="validation_data" style="width: 390px; height: 20px; margin-bottom: 0px;" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1">'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.validation_data = ctrl.$viewValue;
      };
      scope.$watch("validation_data.nEvents", function(elem){ //watch nEvents -> is user leaves empty remove nEvents, as not to save null
        if (!elem){
          delete(scope.validation_data.nEvents);
        }
      });
    }
  }
});


testApp.directive("listEdit", function(){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in analysis_data">'+
    '     <span ng-hide="editable[$index]">'+
    '       {{elem}}'+
    '     </span>'+
    '     <span ng-show="editable[$index] && not_editable_list.indexOf(columnName)==-1">'+
    '       <input type="text" ng-model="new_id" class="input-xxlarge" ng-disabled="not_editable_list.indexOf(columnName)!=-1">'+
    '       <a ng-click="analysis_data[$index] = new_id; editable[$index] = false;" >'+
    '         <i class="icon-plus-sign"></i>'+
    '       </a>'+
    '       <a ng-click="editable[$index]=!editable[$index]; new_id=analysis_data[$index];">'+
    '         <i class="icon-minus"></i>'+
    '       </a>'+
    '     </span>'+
    '     <span ng-hide="editable[$index] || not_editable_list.indexOf(columnName)!=-1">'+
    '       <a ng-click="editable[$index]=!editable[$index]; new_id=analysis_data[$index];">'+
    '         <i class="icon-wrench"></i>'+
    '       </a>'+
    '       <a ng-click="remove($index)">'+
    '         <i class="icon-remove-sign"></i>'+
    '       </a>'+
    '     <span>'+
    '   </li>'+
    '  </ul>'+
    '    <form class="form-inline" ng-hide="not_editable_list.indexOf(columnName)!=-1">'+
    '      <a ng-click="add_analysis_id=!add_analysis_id;">'+
    '        <i class="icon-plus" ng-hide="add_analysis_id"></i>'+
    '        <i class="icon-minus" ng-show="add_analysis_id"></i>'+
    '      </a>'+
    '      <input type="text" ng-model="new_analysis_id" ng-show="add_analysis_id" class="input-xxlarge"></i>'+
    '      <i class="icon-plus-sign" ng-click="pushNewAnalysisID()" ng-show="add_analysis_id"></i>'+
    '    </form>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.analysis_data = ctrl.$viewValue;
        scope.new_analysis_id = "";
        scope.editable = {};
        scope.new_id = "";
        scope.columnName = scope.$eval(attr.column);
      };

      scope.remove = function(index){
        scope.analysis_data.splice(index, 1);
      };

      scope.pushNewAnalysisID = function(){
        scope.analysis_data.push(scope.new_analysis_id);
        scope.add_analysis_id = false;
        scope.new_analysis_id = "";
      };
    }
  }
});