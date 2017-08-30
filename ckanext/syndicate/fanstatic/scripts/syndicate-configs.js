ckan.module('syndicate-profile-remove', function($, _) {
    "use strict";
    return {
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
        },
        _onClick: function(e) {
          e.preventDefault();
          var profileId = this.el.siblings('input[type="hidden"]').val();
          console.log(this.lookUpProfiles());
          if (profileId) {
              $('#syndicate_remove_profiles').append($('<input>', {
                  name: 'syndicate_remove_profiles',
                  type: 'hidden',
                  value: profileId
              }));
            // $.ajax({
            //     'url': ckan.SITE_ROOT + '/syndicate-config/remove',
            //     'method': 'POST',
            //     'data': {profileId: profileId},
            //     'success': function(data) {
            //         if (data.success) {
            //             $(e.target).closest('div.syndicate-profile-item').remove();
            //         }
            //     }
            // });
          } else {
            //   $(e.target).closest('div.syndicate-profile-item').remove();
          }
          $(e.target).closest('div.syndicate-profile-item').remove();
          if (this.lookUpProfiles().length == 1) {
              $('.syndicate-profile-item > .syndicate-profile-item-remove').remove();
          }
          this.initialSetIndexCheckbox();
        },
        lookUpProfiles: function() {
            var profilesNumber = $('.syndicate-profile-item');

            return profilesNumber;
        },
        initialSetIndexCheckbox: function() {
            var data = $('.syndicate-profile-item');
            console.log(data);
            data.each(function(index, elem) {
                // console.log(index);
                var checkbox = $(elem).find('input[type="checkbox"]');
                var attrName = 'syndicate_replicate_organization_';
                checkbox.attr('name', attrName + index);
            });
        }
    };
});

ckan.module('syndicate-profiles-add', function($, _) {
    "use strict";

    return {
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
          this.initialSetIndexCheckbox();
          this.lookUpProfiles().length > 1 && this.initialRemoveBtns();
        },
        _onClick: function(e) {
            e.preventDefault();
            var data = this.el.siblings('.syndicate-config-items').find('.syndicate-profile-item').eq(0);
            var firstCloned = data.clone();

            // Create remove btn element for our cloned form set.
            var removeBtnElem = $('<a>', {
                    class: 'btn btn-danger btn-small syndicate-profile-item-remove',
                    'data-module': 'syndicate-profile-remove',
                    href: '#',
                    title: 'Delete',
                    html: '<i class="icon-remove"></i>'
                });
            
            // Cleanup the form set
            this.cleanUpFormItems(firstCloned);
            var removeBtnCloned = firstCloned.find('.syndicate-profile-item-remove')[0];
            var removeBtnLookUp = data.find('.syndicate-profile-item-remove').length;

            // If there is no remove btn in the cloned form set, add one
            !removeBtnLookUp && firstCloned.append(removeBtnElem);

            // Initialize remove btn
            ckan.module.initializeElement(removeBtnLookUp ? removeBtnCloned : removeBtnElem[0])

            // Add form set into the list of forms
            $('.syndicate-config-items').append(firstCloned);
            this.initialSetIndexCheckbox();
            // Add remove btn to the core(first) form set
            if (!removeBtnLookUp) {
                this.lookUpProfiles().length > 1 && data.append($('<a>', {
                        class: 'btn btn-danger btn-small syndicate-profile-item-remove',
                        'data-module': 'syndicate-profile-remove',
                        href: '#',
                        title: 'Delete',
                        html: '<i class="icon-remove"></i>'
                    }));
            }
        },
        cleanUpFormItems: function(formSet) {
            formSet.find('.syndicate-profile-item-remove').attr('data-module-profileid', '');
            formSet.find('input[type="text"]').each(function(index, item) {
                $(this).val('');
            });
            formSet.find('input[type="hidden"]').val('');
            formSet.find('input[type="checkbox"]').prop( "checked", false );
        },
        lookUpProfiles: function() {
            var profilesNumber = $('.syndicate-profile-item');

            return profilesNumber;
        },
        initialRemoveBtns: function() {
            var data = this.el.siblings('.syndicate-config-items').find('.syndicate-profile-item');
            data.each(function(index, elem) {
                var removeBtnElem = $('<a>', {
                        class: 'btn btn-danger btn-small syndicate-profile-item-remove',
                        'data-module': 'syndicate-profile-remove',
                        href: '#',
                        title: 'Delete',
                        html: '<i class="icon-remove"></i>'
                    });
                ckan.module.initializeElement(removeBtnElem[0])
                $(elem).append(removeBtnElem);
            });
        },
        initialSetIndexCheckbox: function() {
            var data = this.el.siblings('.syndicate-config-items').find('.syndicate-profile-item');
            data.each(function(index, elem) {
                // console.log(index);
                var checkbox = $(elem).find('input[type="checkbox"]');
                var attrName = 'syndicate_replicate_organization_';
                checkbox.attr('name', attrName + index);
            });
        }
    };
});
