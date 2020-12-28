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
        ...props
    },
    on: {
        focuspointchange: onChange
    }
});

export const Centre = Template.bind({});
Centre.args = {
};

export const NotCentre = Template.bind({});
NotCentre.args = {
    focusX: 0.666,
    focusY: 0.333
};
