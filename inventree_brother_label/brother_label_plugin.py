"""Brother label printing plugin for InvenTree.

Supports direct printing of labels to networked label printers, using the brother_label library.
"""

# Required brother_label libs
from brother_label import BrotherLabel

# translation
from django.utils.translation import gettext_lazy as _

# printing options
from rest_framework import serializers

from inventree_brother_label.version import BROTHER_LABEL_PLUGIN_VERSION

# InvenTree plugin libs
from plugin import InvenTreePlugin
from plugin.mixins import LabelPrintingMixin, SettingsMixin

# Image library
from PIL import ImageOps

brother = BrotherLabel()

def get_model_choices():
    """
    Returns a list of available printer models
    """

    return [(id, device.name) for (id, device) in brother.devices.items()]


def get_label_choices():
    """
    Return a list of available label types
    """

    ids = set([('automatic', 'Automatic')])

    for device in brother.devices.values():
        for label in device.labels:
            for identifier in label.identifiers:
                ids.add((identifier, label.name))

    return list(ids)


def get_rotation_choices():
    """
    Return a list of available rotation angles
    """

    return [(f"{degree}", f"{degree}°") for degree in [0, 90, 180, 270]]


class BrotherLabelSerializer(serializers.Serializer):
    """Custom serializer class for BrotherLabelPlugin.

    Used to specify printing parameters at runtime
    """

    copies = serializers.IntegerField(
        default=1,
        label=_('Copies'),
        help_text=_('Number of copies to print'),
    )


class BrotherLabelPlugin(LabelPrintingMixin, SettingsMixin, InvenTreePlugin):

    AUTHOR = "Dean Gardiner"
    DESCRIPTION = "Label printing plugin for Brother printers"
    VERSION = BROTHER_LABEL_PLUGIN_VERSION

    NAME = "Brother Labels"
    SLUG = "brother_label"
    TITLE = "Brother Label Printer"

    PrintingOptionsSerializer = BrotherLabelSerializer

    # Use background printing
    BLOCKING_PRINT = False

    SETTINGS = {
        'MODEL': {
            'name': _('Model'),
            'description': _('Select model of Brother printer'),
            'choices': get_model_choices,
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
        'USB_DEVICE': {
            'name': _('USB Device'),
            'description': _('USB device identifier of the label printer (VID:PID/SERIAL)'),
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
        'COMPRESSION': {
            'name': _('Compression'),
            'description': _('Enable image compression option (required for some printer models)'),
            'validator': bool,
            'default': False,
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

        # Printing options requires a modern-ish InvenTree backend,
        # which supports the 'printing_options' keyword argument
        options = kwargs.get('printing_options', {})
        n_copies = int(options.get('copies', 1))

        # Look for png data in kwargs (if provided)
        label_image = kwargs.get('png_file', None)

        if not label_image:
            # Convert PDF to PNG
            pdf_data = kwargs['pdf_data']
            label_image = self.render_to_png(label=None, pdf_data=pdf_data)

        # Read settings
        model = self.get_setting('MODEL')
        ip_address = self.get_setting('IP_ADDRESS')
        usb_device = self.get_setting('USB_DEVICE')
        label_type = self.get_setting('TYPE')
        cut = self.get_setting('AUTO_CUT')
        compress = self.get_setting('COMPRESSION')
        hq = self.get_setting('HQ')

        # Automatic label selection
        if label_type == 'automatic':
            if not kwargs.get('pdf_data', None):
                raise Exception('PDF required for automatic label type selection')
            
            pdf = PdfReader(kwargs['pdf_data'])
            rect = pdf.pages[0].cropbox
            
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

        # Select appropriate identifier and backend
        target = ''
        backend = ''

        # check IP address first, then USB
        if ip_address:
            target = f'tcp://{ip_address}'
            backend = 'network'
        elif usb_device:
            target = f'usb://{usb_device}'
            backend = 'pyusb'
        else:
            # Raise error when no backend is defined
            raise ValueError("No IP address or USB device defined.")

        # Print label
        brother.print(
            label_type,
            [label_image],
            cut=cut,
            device=device,
            compress=compress,
            hq=hq,
            rotate=rotation,
            target=target,
            backend=backend,
            blocking=True
        )
