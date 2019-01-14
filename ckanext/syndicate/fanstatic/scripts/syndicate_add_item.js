ckan.module('syndicate-add-profile', function($, _) {
    "use strict";

    return {
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
        },
        _onClick: function(e) {
            var data = $('.syndicate-profile-item').last();
            var old_index = parseInt(data.attr('index'));
            var new_index = old_index + 1;
            var cloned_data = data.clone();
            this.cleanUpFormFields(cloned_data, old_index, new_index);
            $('.syndicate-profile-items').append(cloned_data);
            $('[data-module="syndicate-remove-profile"]', document.body).each(function (index, element) {
                ckan.module.initializeElement(this);
            });
        },
        cleanUpFormFields: function(form_fields, old_index, new_index) {
            form_fields.attr('index', new_index);
            form_fields.find('input[type="text"], input[type="hidden"], select, label').each(function(index, item) {
                if ($(this).is('label')) {
                    var new_for = $(this).attr('for').replace("_" + old_index, "_" + new_index);
                    $(this).attr('for', new_for);
                }else {
                    var new_name = item.name.replace("_" + old_index, "_" + new_index);
                    $(this).val('').attr('name', new_name).attr('id', new_name);
                    if ($(this).is('select')) {
                        $(this).val('no');
                    };
                };
            });
            form_fields.find('[data-module="syndicate-remove-profile"]').removeAttr('data-module-profile_id');
        }
    };
});