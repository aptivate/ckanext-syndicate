ckan.module('syndicate-remove-profile', function($, _) {
    "use strict";

    return {
        options : {
            profile_id: null,
        },
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
        },
        _onClick: function(event) {
        	event.preventDefault();
        	var options = this.options;
        	if (!options.profile_id) {
        		$(this.el).closest('div.syndicate-profile-item').remove();
        	}else {
        		var data_dict = {'id': options.profile_id};
        		var client = this.sandbox.client;
        		client.call('POST', 'syndicate_remove_profile', data_dict, this._onResponse);
        	};
        },
        _onResponse: function(json) {
        	var result = json.result;
        	if (result.success) {
        		$(this.el).closest('div.syndicate-profile-item').remove();
        	};
        }
    };
});