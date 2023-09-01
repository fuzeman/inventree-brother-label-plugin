"""Brother label printing plugin for InvenTree.

Supports direct printing of labels to networked label printers, using the brother_label library.
"""

# Required brother_label libs
from brother_label import BrotherLabel

# translation
from django.utils.translation import ugettext_lazy as _

from inventree_brother_label.version import BROTHER_LABEL_PLUGIN_VERSION

# InvenTree plugin libs
from plugin import InvenTreePlugin
from plugin.mixins import LabelPrintingMixin, SettingsMixin

# PDF library
import poppler

brother = BrotherLabel()


def get_device_choices():
    """
    Returns a list of available printer models
    """

    return [(id, device.name) for (id, device) in brother.devices.items()]


def get_label_choices():
    """
    Return a list of available label types
    """

    ids = set('automatic')

    for device in brother.devices.values():
        for label in device.labels:
            for identifier in label.identifiers:
                ids.add(identifier)

    return list(ids)


def get_rotation_choices():
    """
    Return a list of available rotation angles
    """

    return [(f"{degree}", f"{degree}°") for degree in [0, 90, 180, 270]]


class BrotherLabelPlugin(LabelPrintingMixin, SettingsMixin, InvenTreePlugin):

    AUTHOR = "Dean Gardiner"
    DESCRIPTION = "Label printing plugin for Brother printers"
    VERSION = BROTHER_LABEL_PLUGIN_VERSION

    NAME = "Brother Labels"
    SLUG = "brother_label"
    TITLE = "Brother Label Printer"

    # Use background printing
    BLOCKING_PRINT = False

    SETTINGS = {
        'DEVICE': {
            'name': _('Device'),
            'description': _('Select device'),
            'choices': get_device_choices,
            'default': 'PT-P750W',
        },
        'TYPE': {
            'name': _('Type'),
            'description': _('Select label media type'),
            'choices': get_label_choices,
            'default': '12',
        },
        'IP_ADDRESS': {
            'name': _('IP Address'),
            'description': _('IP address of the brother label printer'),
            'default': '',
        },
        'AUTO_CUT': {
            'name': _('Auto Cut'),
            'description': _('Cut each label after printing'),
            'validator': bool,
            'default': True,
        },
        'ROTATION': {
            'name': _('Rotation'),
            'description': _('Rotation of the image on the label'),
            'choices': get_rotation_choices,
            'default': '0',
        },
        'HQ': {
            'name': _('High Quality'),
            'description': _('Enable high quality option (required for some printers)'),
            'validator': bool,
            'default': True,
        },
    }

    def print_label(self, **kwargs):
        """
        Send the label to the printer
        """

        # TODO: Add padding around the provided image, otherwise the label does not print correctly
        # ^ Why? The wording in the underlying brother_label library ('dots_printable') seems to suggest
        # at least that area is fully printable.
        # TODO: Improve label auto-scaling based on provided width and height information

        # Extract width (x) and height (y) information
        # width = kwargs['width']
        # height = kwargs['height']
        # ^ currently this width and height are those of the label template (before conversion to PDF
        # and PNG) and are of little use

        device = self.get_setting('DEVICE')
        ip_address = self.get_setting("IP_ADDRESS")
        label_type = self.get_setting('TYPE')
        cut = self.get_setting('AUTO_CUT')
        hq = self.get_setting('HQ')

        # Retrieve PNG
        if kwargs.get('pdf_data', None):
            im = self.render_to_png(label=None, pdf_data=kwargs['pdf_data'])
        else:
            im = kwargs['png_file']

        # Automatic label selection
        if label_type == 'automatic':
            if not kwargs.get('pdf_data', None):
                raise Exception('PDF required for automatic label type selection')
            
            document = poppler.load_from_data(kwargs['pdf_data'])
            page = document.pages[0]
            rect = page.page_rect()
            
            label_type = None

            for label in brother.devices[device].labels:
                if label.tape_size[1] == rect.height:
                    label_type = label.identifiers[0]
                    break
            
            if not label_type:
                raise Exception('Unable to find matching label type')

        # Calculate rotation
        rotation = int(self.get_setting('ROTATION')) + 90
        rotation = rotation % 360

        # Print label
        brother.print(
            label_type,
            [im],
            cut=cut,
            device=device,
            hq=hq,
            rotate=rotation,
            target=f'tcp://{ip_address}',
            backend='network',
            blocking=True
        )
