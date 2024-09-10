"""Brother label printing plugin for InvenTree.

Supports direct printing of labels to networked label printers, using the brother_label library.
"""

# Required brother_label libs
from brother_label import BrotherLabel

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# printing options
from rest_framework import serializers

from inventree_brother_label.version import BROTHER_LABEL_PLUGIN_VERSION

# InvenTree plugin libs
from plugin import InvenTreePlugin
from plugin.mixins import LabelPrintingMixin, SettingsMixin
from report.models import LabelOutput, LabelTemplate

brother = BrotherLabel()


def get_model_choices():
    """
    Returns a list of available printer models
    """

    return [(id, device.name) for (id, device) in brother.devices.items()]


def get_media_choices():
    """
    Return a list of available label types
    """

    ids = set([])

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

    media = serializers.ChoiceField(
        label=_('Media'),
        help_text=_('Select label media type'),
        choices=get_media_choices(),
        default='12',
    )

    rotation = serializers.ChoiceField(
        label=_('Rotation'),
        help_text=_('Rotation of the image on the label'),
        choices=get_rotation_choices(),
        default='0',
    )

    copies = serializers.IntegerField(
        default=1,
        label=_('Copies'),
        help_text=_('Number of copies to print'),
    )

    autocut = serializers.BooleanField(
        default=True,
        label=_('Auto Cut'),
        help_text=_('Automatically cut labels')
    )

    autocut_every = serializers.IntegerField(
        default=1,
        label=_('Auto Cut Every'),
        help_text=_('Cut every n-th label')
    )

    autocut_end = serializers.BooleanField(
        default=True,
        label=_('Auto Cut End'),
        help_text=_('Feed and cut after last label is printed')
    )

    halfcut = serializers.BooleanField(
        default=True,
        label=_('Half Cut'),
        help_text=_('Half-cut labels')
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

    def print_labels(
        self, label: LabelTemplate, output: LabelOutput, items: list, request, **kwargs
    ):
        """Handle printing of the provided labels.

        Note that we override the entire print_labels method for this plugin.
        """

        # Initial state for the output print job
        output.progress = 0
        output.complete = False
        output.save()

        n_items = len(items)

        if n_items <= 0:
            raise ValidationError(_('No items provided to print'))

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

        media = options.get('media', '12')
        copies = int(options.get('copies', 1))
        autocut = options.get('autocut', True)
        autocut_every = int(options.get('autocut_every', 1))
        autocut_end = options.get('autocut_end', True)
        halfcut = options.get('halfcut', True)

        # Read settings
        model = self.get_setting('MODEL')
        ip_address = self.get_setting('IP_ADDRESS')
        usb_device = self.get_setting('USB_DEVICE')
        compress = self.get_setting('COMPRESSION')
        hq = self.get_setting('HQ')

        # Calculate rotation
        rotation = int(options.get('rotation', 0)) + 90
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

        # Render labels
        labels = []

        for item in items:
            pdf_file = self.render_to_pdf(label, item, request, **kwargs)
            pdf_data = pdf_file.get_document().write_pdf()

            labels.append(self.render_to_png(
                label, item, request, pdf_data=pdf_data, **kwargs
            ))

        # Print label
        brother.print(
            media,
            [label for label in labels for x in range(copies)],
            autocut=autocut,
            autocut_every=autocut_every,
            autocut_end=autocut_end,
            halfcut=halfcut,
            device=model,
            compress=compress,
            hq=hq,
            rotate=rotation,
            target=target,
            backend=backend,
            blocking=True
        )

        # Mark the output as complete
        output.complete = True
        output.progress = 100
        output.output = None

        output.save()
