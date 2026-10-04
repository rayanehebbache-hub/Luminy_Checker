"use strict";

document.addEventListener('DOMContentLoaded', () => {
    // on recupere l'id de l'utilisateur (on n'oublie pas
    // de convertir en int)
    const userId = parseInt(document.body.dataset.userId);
    initAllPCs(userId);
});

// fonction pour attribuer la bonne couleur a un pc
// vert: libre
// bleu: occupe par moi
// rouge: occupe par un autre utilisateur
function setPCColor(pc, takenBy, userId) {
    if (!takenBy) {
        pc.style.background = "green";
    } else if (parseInt(takenBy) === userId) {
        pc.style.background = "blue";
    } else {
        pc.style.background = "red";
    }
}

// fonction pour initialiser la couleur d'un pc
function initPCColors(userId) {
    const pcs = document.querySelectorAll('.pc');
    pcs.forEach(pc => {
        const takenBy = pc.dataset.user;
        setPCColor(pc, takenBy, userId);
    });
}

// fonction qui associe la bonne couleur a tous les pc
function initAllPCs(userId) {
    const pcs = document.querySelectorAll('.pc');
    // on recupere qui a quel pc via data-user dans la vue
    // computers et pour chque pc on appelle setPCColor pour
    // lui attribuer la bonne couleur
    pcs.forEach(pc => {
        const takenBy = pc.dataset.user;
        setPCColor(pc, takenBy, userId);
    });
    handleClick(userId);
}

// fonction pour la gestion de pc (on prendre un ou en
// libere un)
function handleClick(userId) {
    // button[data-id] pour selectionner tous les bouttons
    // qui on un data-id (comme en css)
    const buttons = document.querySelectorAll('button[data-id]');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const pcId = parseInt(btn.dataset.id);
            const pc = document.querySelector(`#pc-${pcId}`);
            const takenBy = pc.dataset.user;
            // cas: j'occupe pas ce pc
            if (!takenBy) {
                fetch('/take_computer', {
                    method: 'POST',
                    // ici on dit que les donnees sont encodees
                    // comme un formulaire HTML classique
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `computer_id=${pcId}`
                // location.reload() pour recharger la page
                }).then(() => location.reload());
            // cas: j'occupe ce pc
            } else if (parseInt(takenBy) === userId) {
                fetch('/release_computer', {
                    method: 'POST'
                }).then(() => location.reload());
            }
        });
    });
}