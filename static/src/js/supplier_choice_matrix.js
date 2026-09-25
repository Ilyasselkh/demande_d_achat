/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class MatrixDialog extends Dialog {
    static props = { ...Dialog.props, onDismiss: Function };

    async dismiss() {
        if (await this.props.onDismiss()) {
            return super.dismiss();
        }
    }
}

export class SupplierChoiceMatrixDialog extends Component {
    static template = "demande_d_achat.SupplierChoiceMatrixDialog";
    static components = { Dialog: MatrixDialog };
    static props = { requestId: Number, close: Function };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ loading: true, saving: false, readingFiles: false, dirty: false, data: null });
        this.nextTempId = -1;
        onWillStart(() => this.load());
    }

    get suggestedSupplier() {
        if (!this.state.data) {
            return null;
        }
        return this.state.data.suppliers.find(
            (supplier) => supplier.id === this.state.data.suggested_supplier_id
        );
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call(
            "purchase.request", "get_supplier_matrix", [[this.props.requestId]]
        );
        this.syncDerogation();
        this.state.loading = false;
        this.state.dirty = false;
    }

    updateSupplierName(supplier, event) {
        supplier.name = event.target.value;
        this.recalculate();
        this.markDirty();
    }

    syncDerogation() {
        const data = this.state.data;
        data.derogation_mode = Boolean(data.selected_supplier_id &&
            data.suggested_supplier_id &&
            data.selected_supplier_id !== data.suggested_supplier_id);
    }

    updateSelectedSupplier(event) {
        this.state.data.selected_supplier_id = Number(event.target.value) || false;
        this.syncDerogation();
        this.markDirty();
    }

    updateDerogationReason(event) {
        this.state.data.derogation_reason = event.target.value;
        this.markDirty();
    }

    updateScore(evaluation, event) {
        evaluation.score = event.target.value;
        evaluation.score_set = event.target.value !== "";
        this.recalculate();
        this.markDirty();
    }

    updateComment(evaluation, event) {
        evaluation.comment = event.target.value;
        this.markDirty();
    }

    toggleApplicable(evaluation, event) {
        evaluation.applicable = !event.target.checked;
        this.recalculate();
        this.markDirty();
    }

    addSupplier() {
        const id = this.nextTempId--;
        this.state.data.suppliers.push({
            id, sequence: this.state.data.suppliers.length + 1,
            name: "", total: 0, quotations: [],
        });
        for (const criterion of this.state.data.criteria) {
            criterion.evaluations[id] = {
                id: null, score: 0, score_set: false, comment: "", applicable: true, weighted: 0,
            };
        }
        this.markDirty();
    }

    async uploadQuotation(supplier, event) {
        const files = [...event.target.files];
        event.target.value = "";
        this.state.readingFiles = true;
        for (const file of files) {
            try {
                const content = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result.split(",")[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                });
                supplier.quotations.push({ id: null, key: this.nextTempId--, name: file.name, content });
                this.markDirty();
            } catch (error) {
                this.notification.add(error.data?.message || error.message, { type: "danger" });
            }
        }
        this.state.readingFiles = false;
    }

    removeQuotation(supplier, attachment) {
        supplier.quotations = supplier.quotations.filter((item) => item !== attachment);
        this.markDirty();
    }

    removeSupplier(supplier) {
        if (this.state.data.suppliers.length <= 1) {
            this.notification.add("La matrice doit conserver au moins un fournisseur.", { type: "warning" });
            return;
        }
        const remove = () => {
            if (this.state.data.selected_supplier_id === supplier.id) {
                this.state.data.selected_supplier_id = false;
            }
            this.state.data.suppliers = this.state.data.suppliers.filter((item) => item !== supplier);
            this.state.data.suppliers.forEach((item, index) => item.sequence = index + 1);
            this.recalculate();
            this.markDirty();
        };
        if (supplier.name || supplier.quotations.length || this.state.data.criteria.some(
            (criterion) => {
                const evaluation = criterion.evaluations[supplier.id];
                return evaluation.score_set || evaluation.comment || !evaluation.applicable;
            }
        )) {
            this.dialog.add(ConfirmationDialog, {
                    title: "Supprimer le fournisseur",
                    body: `Les notes, commentaires et devis de ${supplier.name || "ce fournisseur"} seront retirés de la matrice. Continuer ?`,
                    confirm: remove,
                    confirmLabel: "Supprimer",
                    cancelLabel: "Annuler",
            });
        } else {
            remove();
        }
    }

    async downloadMatrix() {
        if (this.state.dirty) {
            this.notification.add("Enregistrez la matrice avant de télécharger le PDF.", { type: "warning" });
            return;
        }
        const reportAction = await this.orm.call(
            "purchase.request",
            "action_download_supplier_matrix",
            [[this.props.requestId]]
        );
        return this.action.doAction(reportAction);
    }

    markDirty() {
        this.state.dirty = true;
    }

    recalculate() {
        for (const supplier of this.state.data.suppliers) {
            const total = this.state.data.criteria.reduce((total, criterion) => {
                const evaluation = criterion.evaluations[supplier.id];
                return total + (evaluation.applicable && evaluation.score_set
                    ? (Number(evaluation.score) || 0) * criterion.weight : 0);
            }, 0);
            supplier.total = Math.round(total * 100) / 100;
        }
        const named = this.state.data.suppliers.filter((supplier) => supplier.name.trim());
        this.state.data.suggested_supplier_id = named.length
            ? named.reduce((best, supplier) => supplier.total > best.total ? supplier : best).id
            : null;
        this.syncDerogation();
    }

    async saveMatrix() {
        if (!this.state.dirty || this.state.saving || this.state.readingFiles) {
            return;
        }
        const data = this.state.data;
        this.syncDerogation();
        if (data.derogation_mode && !(data.derogation_reason || "").trim()) {
            this.notification.add("Veuillez renseigner le motif de la dérogation.", { type: "warning" });
            return;
        }
        const payload = {
            selected_supplier_index: data.suppliers.findIndex(
                (supplier) => supplier.id === data.selected_supplier_id
            ),
            derogation_mode: data.derogation_mode,
            derogation_reason: data.derogation_reason,
            suppliers: data.suppliers.map((supplier) => ({
                id: supplier.id > 0 ? supplier.id : null,
                name: supplier.name,
                quotations: supplier.quotations.map(({ id, name, content }) => ({ id, name, content })),
                evaluations: Object.fromEntries(data.criteria.map((criterion) => {
                    const { score, score_set, comment, applicable } = criterion.evaluations[supplier.id];
                    return [criterion.id, { score, score_set, comment, applicable }];
                })),
            })),
        };
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call(
                "purchase.request", "save_supplier_matrix", [[this.props.requestId], payload]
            );
            this.state.dirty = false;
            this.notification.add("Matrice enregistrée.", { type: "success" });
        } catch (error) {
            this.notification.add(error.data?.message || error.message, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    confirmClose() {
        if (this.state.saving || this.state.readingFiles) {
            this.notification.add("Patientez jusqu'à la fin de l'enregistrement des fichiers.", { type: "warning" });
            return Promise.resolve(false);
        }
        if (!this.state.dirty) {
            return Promise.resolve(true);
        }
        return new Promise((resolve) => this.dialog.add(ConfirmationDialog, {
            title: "Modifications non enregistrées",
            body: "Les changements apportés à la matrice seront perdus. Fermer sans enregistrer ?",
            confirm: () => resolve(true),
            cancel: () => resolve(false),
            confirmLabel: "Fermer sans enregistrer",
            cancelLabel: "Continuer",
        }));
    }

    async closeMatrix() {
        if (await this.confirmClose()) {
            this.props.close();
        }
    }
}

export class SupplierChoiceMatrix extends Component {
    static template = "demande_d_achat.SupplierChoiceMatrix";
    static props = { ...standardFieldProps };

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    }

    async openMatrix() {
        if (!this.props.record.resId) {
            this.notification.add("Enregistrez la demande avant d'ouvrir la matrice.", {
                type: "warning",
            });
            return;
        }
        if (this.props.record.isDirty) {
            const saved = await this.props.record.save();
            if (!saved) {
                return;
            }
        }
        this.dialog.add(SupplierChoiceMatrixDialog, {
            requestId: this.props.record.resId,
        });
    }
}

registry.category("fields").add("supplier_choice_matrix", {
    component: SupplierChoiceMatrix,
    supportedTypes: ["char"],
});
