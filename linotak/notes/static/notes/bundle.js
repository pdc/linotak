var app=function(){"use strict";function t(){}function e(t){return t()}function n(){return Object.create(null)}function o(t){t.forEach(e)}function i(t){return"function"==typeof t}function c(t,e){return t!=t?e==e:t!==e||t&&"object"==typeof t||"function"==typeof t}function r(t,e){t.appendChild(e)}function u(t){t.parentNode.removeChild(t)}function s(t){return document.createElementNS("http://www.w3.org/2000/svg",t)}function l(t,e,n){null==n?t.removeAttribute(e):t.getAttribute(e)!==n&&t.setAttribute(e,n)}function a(t,e,n){t.setAttributeNS("http://www.w3.org/1999/xlink",e,n)}let d;function f(t){d=t}function h(){if(!d)throw new Error("Function called outside component initialization");return d}function m(){const t=h();return(e,n)=>{const o=t.$$.callbacks[e];if(o){const i=function(t,e){const n=document.createEvent("CustomEvent");return n.initCustomEvent(t,!1,!1,e),n}(e,n);o.slice().forEach(e=>{e.call(t,i)})}}}const p=[],g=[],$=[],w=[],v=Promise.resolve();let y=!1;function x(t){$.push(t)}let E=!1;const b=new Set;function _(){if(!E){E=!0;do{for(let t=0;t<p.length;t+=1){const e=p[t];f(e),k(e.$$)}for(f(null),p.length=0;g.length;)g.pop()();for(let t=0;t<$.length;t+=1){const e=$[t];b.has(e)||(b.add(e),e())}$.length=0}while(p.length);for(;w.length;)w.pop()();y=!1,E=!1,b.clear()}}function k(t){if(null!==t.fragment){t.update(),o(t.before_update);const e=t.dirty;t.dirty=[-1],t.fragment&&t.fragment.p(t.ctx,e),t.after_update.forEach(x)}}const X=new Set;function Y(t,e){-1===t.$$.dirty[0]&&(p.push(t),y||(y=!0,v.then(_)),t.$$.dirty.fill(0)),t.$$.dirty[e/31|0]|=1<<e%31}function M(c,r,s,l,a,h,m=[-1]){const p=d;f(c);const g=r.props||{},$=c.$$={fragment:null,ctx:null,props:h,update:t,not_equal:a,bound:n(),on_mount:[],on_destroy:[],before_update:[],after_update:[],context:new Map(p?p.$$.context:[]),callbacks:n(),dirty:m,skip_bound:!1};let w=!1;if($.ctx=s?s(c,g,(t,e,...n)=>{const o=n.length?n[0]:e;return $.ctx&&a($.ctx[t],$.ctx[t]=o)&&(!$.skip_bound&&$.bound[t]&&$.bound[t](o),w&&Y(c,t)),e}):[],$.update(),w=!0,o($.before_update),$.fragment=!!l&&l($.ctx),r.target){if(r.hydrate){const t=function(t){return Array.from(t.childNodes)}(r.target);$.fragment&&$.fragment.l(t),t.forEach(u)}else $.fragment&&$.fragment.c();r.intro&&((v=c.$$.fragment)&&v.i&&(X.delete(v),v.i(y))),function(t,n,c){const{fragment:r,on_mount:u,on_destroy:s,after_update:l}=t.$$;r&&r.m(n,c),x(()=>{const n=u.map(e).filter(i);s?s.push(...n):o(n),t.$$.on_mount=[]}),l.forEach(x)}(c,r.target,r.anchor),_()}var v,y;f(p)}function C(t){let e,n;function o(o){e=o.clientX,n=o.clientY,t.dispatchEvent(new CustomEvent("panstart",{detail:{x:e,y:n}})),window.addEventListener("mousemove",i),window.addEventListener("mouseup",c)}function i(o){const i=o.clientX-e,c=o.clientY-n;e=o.clientX,n=o.clientY,t.dispatchEvent(new CustomEvent("panmove",{detail:{x:e,y:n,dx:i,dy:c}}))}function c(o){e=o.clientX,n=o.clientY,t.dispatchEvent(new CustomEvent("panend",{detail:{x:e,y:n}})),window.removeEventListener("mousemove",i),window.removeEventListener("mouseup",c)}return t.addEventListener("mousedown",o),{destroy(){t.removeEventListener("mousedown",o)}}}function L(e){let n,c,d,f,h,m,p,g,$,w,v,y,x,E,b,_,k,X,Y,M,L;return{c(){var t;t="div",n=document.createElement(t),c=s("svg"),d=s("image"),f=s("rect"),$=s("rect"),E=s("circle"),a(d,"xlink:href",e[4]),l(d,"width",e[0]),l(d,"height",e[1]),l(f,"x",h=e[12]+.5),l(f,"y",m=e[13]+.5),l(f,"width",p=e[7]-1),l(f,"height",g=e[8]-1),l(f,"stroke-width","1"),l(f,"stroke","#F56"),l(f,"fill","none"),l($,"x",w=e[10]+.5),l($,"y",v=e[11]+.5),l($,"width",y=e[5]-1),l($,"height",x=e[6]-1),l($,"stroke-width","1"),l($,"stroke","#0BA"),l($,"fill","none"),l(E,"cx",b=e[2]*e[0]),l(E,"cy",_=e[3]*e[1]),l(E,"r",k=32),l(E,"stroke-width","1"),l(E,"stroke","#B0A"),l(E,"fill","rgba(187, 0, 170, 0.1)"),l(c,"class","im"),l(c,"width",e[0]),l(c,"height",e[1]),l(c,"viewBox",Y="0 0 "+e[0]+" "+e[1]),l(n,"class","focus-point")},m(o,u){var s,l,a,h,m;!function(t,e,n){t.insertBefore(e,n||null)}(o,n,u),r(n,c),r(c,d),e[15](d),r(c,f),r(c,$),r(c,E),M||(L=[(m=X=C.call(null,E),m&&i(m.destroy)?m.destroy:t),(s=E,l="panmove",a=e[14],s.addEventListener(l,a,h),()=>s.removeEventListener(l,a,h))],M=!0)},p(t,[e]){16&e&&a(d,"xlink:href",t[4]),1&e&&l(d,"width",t[0]),2&e&&l(d,"height",t[1]),4096&e&&h!==(h=t[12]+.5)&&l(f,"x",h),8192&e&&m!==(m=t[13]+.5)&&l(f,"y",m),128&e&&p!==(p=t[7]-1)&&l(f,"width",p),256&e&&g!==(g=t[8]-1)&&l(f,"height",g),1024&e&&w!==(w=t[10]+.5)&&l($,"x",w),2048&e&&v!==(v=t[11]+.5)&&l($,"y",v),32&e&&y!==(y=t[5]-1)&&l($,"width",y),64&e&&x!==(x=t[6]-1)&&l($,"height",x),5&e&&b!==(b=t[2]*t[0])&&l(E,"cx",b),10&e&&_!==(_=t[3]*t[1])&&l(E,"cy",_),1&e&&l(c,"width",t[0]),2&e&&l(c,"height",t[1]),3&e&&Y!==(Y="0 0 "+t[0]+" "+t[1])&&l(c,"viewBox",Y)},i:t,o:t,d(t){t&&u(n),e[15](null),M=!1,o(L)}}}function A(t,e,n){return e>n*t?[n*t,n]:[e,e/t]}function B(t,e,n){let{src:o}=e,{width:i}=e,{height:c}=e,{focusX:r=.5}=e,{focusY:u=.5}=e;const s=m();let l,a,d,f,p;var $;let w,v,y,x;return $=()=>{const t=document.documentElement.clientWidth,e=document.documentElement.clientHeight;(i>t||c>e)&&(i/c<t/e?(n(0,i*=e/c),n(1,c=e)):(n(1,c*=t/i),n(0,i=t)))},h().$$.on_mount.push($),t.$$set=t=>{"src"in t&&n(4,o=t.src),"width"in t&&n(0,i=t.width),"height"in t&&n(1,c=t.height),"focusX"in t&&n(2,r=t.focusX),"focusY"in t&&n(3,u=t.focusY)},t.$$.update=()=>{3&t.$$.dirty&&n(5,[w,v]=A(1,i,c),w,(n(6,v),n(0,i),n(1,c))),37&t.$$.dirty&&n(10,a=r*(i-w)+.5),74&t.$$.dirty&&n(11,d=u*(c-v)+.5),3&t.$$.dirty&&n(7,[y,x]=A(16/9,i,c),y,(n(8,x),n(0,i),n(1,c))),399&t.$$.dirty&&(y===i?(n(12,f=0),n(13,p=Math.min(c-x,Math.max(0,u*c-.5*x)))):(n(12,f=Math.min(i-y,Math.max(0,r*i-.5*y))),n(13,p=0)))},[i,c,r,u,o,w,v,y,x,l,a,d,f,p,function(t){n(2,r+=t.detail.dx/i),n(3,u+=t.detail.dy/c),n(2,r=Math.max(Math.min(1,r),0)),n(3,u=Math.max(Math.min(1,u),0)),s("focuspointchange",{focusX:r,focusY:u})},function(t){g[t?"unshift":"push"](()=>{l=t,n(9,l)})}]}const S=document.getElementById("focus-ui-form"),N=S.focus_x.value,j=S.focus_y.value,q=document.getElementById("focus-ui"),F=(q.querySelector("label").innerText,q.querySelector("img")),O=F.src,I=F.width,P=F.height;F.remove();const z=new class extends class{$destroy(){!function(t,e){const n=t.$$;null!==n.fragment&&(o(n.on_destroy),n.fragment&&n.fragment.d(e),n.on_destroy=n.fragment=null,n.ctx=[])}(this,1),this.$destroy=t}$on(t,e){const n=this.$$.callbacks[t]||(this.$$.callbacks[t]=[]);return n.push(e),()=>{const t=n.indexOf(e);-1!==t&&n.splice(t,1)}}$set(t){var e;this.$$set&&(e=t,0!==Object.keys(e).length)&&(this.$$.skip_bound=!0,this.$$set(t),this.$$.skip_bound=!1)}}{constructor(t){super(),M(this,t,B,L,c,{src:4,width:0,height:1,focusX:2,focusY:3})}}({target:q,props:{src:O,width:I,height:P,focusX:N,focusY:j}});return z.$on("focuspointchange",t=>{const{detail:{focusX:e,focusY:n}}=t;console.log("handleFocusPointChange"),S.focus_x.value=e,S.focus_y.value=n}),z}();
//# sourceMappingURL=bundle.js.map
