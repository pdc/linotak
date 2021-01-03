import FocusPoint from './FocusPoint.svelte';

export default {
    title: 'Image/FocusPoint',
    component: FocusPoint,
    argTypes: {
        src: { control: 'text' },
        width: { control: 'number' },
        height: { control: 'number' },
        focusX: { control: 'number' },
        focusY: { control: 'number' },
        cropLeft: { control: 'number' },
        cropTop: { control: 'number' },
        cropWidth: { control: 'number' },
        cropHeight: { control: 'number' },
        onChange: { action: 'focuspointchange' },
    },
};

const Template = ({ onChange, ...props }) => ({
    Component: FocusPoint,
    props: {
        src: 'http://pdc.mustardseed.local:8004/media/i/vIEwlP144Wq9iytidAJELQ.jpeg',
        width: 640,
        height: 480,
        focusX: 0.5,
        focusY: 0.5,
        cropLeft: 0.0,
        cropTop: 0.0,
        cropWidth: 1.0,
        cropHeight: 1.0,
        placeholder: '#927e5f',
        ...props
    },
    on: {
        focuspointchange: onChange
    }
});

export const Initial = Template.bind({});
Initial.args = {};

export const Editing = Template.bind({});
Editing.args = {
    width: 960, height: 560,
    focusX: 0.666, focusY: 0.333,
    cropLeft: 0.05, cropTop: 0.05,
    cropWidth: 640.0 / 960.0, cropHeight: 480.0 / 560.0
};
// Note that the same image is used but we pretend it is part of a larger image.
