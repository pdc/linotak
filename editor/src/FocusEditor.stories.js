import FocusEditor from './FocusEditor.svelte';

export default {
    title: 'Image/FocusEditor',
    component: FocusEditor,
    argTypes: {
        src: { control: 'text' },
        width: { control: 'number' },
        height: { control: 'number' },
        label: { control: 'text' },
        focusX: { control: 'number' },
        focusY: { control: 'number' },
    },
};

const Template = (props) => ({
    Component: FocusEditor,
    props: {
        label: 'Focus point',
        src: 'http://pdc.mustardseed.local:8004/media/i/vIEwlP144Wq9iytidAJELQ.jpeg',
        width: 640,
        height: 480,
        focusX: 0.5,
        focusY: 0.5,
        ...props
    },
});

export const Centre = Template.bind({});
Centre.args = {
    label: 'Focus point',
    src: 'http://pdc.mustardseed.local:8004/media/i/vIEwlP144Wq9iytidAJELQ.jpeg',
    width: 640,
    height: 480,
    focusX: 0.5,
    focusY: 0.5,
};

export const Smurfy = (args) => ({
    Component: FocusEditor,
    props: {
        label: 'Focus point',
        src: 'http://pdc.mustardseed.local:8004/media/i/vIEwlP144Wq9iytidAJELQ.jpeg',
        width: 640,
        height: 480,
        // focusX: 0.5,
        // focusY: 0.5,
        ...args,
    }
});