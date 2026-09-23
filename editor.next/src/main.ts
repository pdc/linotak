import wireUp from "./naked";

const imageElt: HTMLImageElement | null =
  document.querySelector("img#focusImage");

const formElt: HTMLFormElement | null = document.forms.item(0);

const imageDataElt: HTMLScriptElement | null =
  document.querySelector("script#imageData");
const imageData = imageDataElt?.text && JSON.parse(imageDataElt.text);

if (imageElt && formElt) {
  wireUp(imageElt, formElt, imageData);
} else {
  let msg = "Cannot activate image editor: ";
  if (!imageElt) {
    msg += "n image with id `focusImage`";
  }
  if (!formElt) {
    if (!imageElt) {
      msg += " and ";
    }
    msg += "no form found";
  }
  console.error(msg);
}
