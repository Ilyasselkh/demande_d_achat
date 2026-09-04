/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class SupplierChoiceMatrixDialog extends Component {
    static template = "demande_d_achat.SupplierChoiceMatrixDialog";
    static components = { Dialog };
    static props = { requestId: Number, close: Function };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ loading: true, data: null });
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
        this.state.loading = false;
    }

    async updateSupplierName(supplier, event) {
        const name = event.target.value.trim();
        if (name !== supplier.name) {
            await this._save("update_supplier_matrix_name", [supplier.id, name]);
        }
    }

    async updateScore(evaluation, event) {
        await this._save("update_supplier_matrix_evaluation", [
            evaluation.id, { score: event.target.value },
        ]);
    }

    async updateComment(evaluation, event) {
        if (event.target.value !== evaluation.comment) {
            await this._save("update_supplier_matrix_evaluation", [
                evaluation.id, { comment: event.target.value },
            ]);
        }
    }

    async toggleApplicable(evaluation, event) {
        await this._save("update_supplier_matrix_evaluation", [
            evaluation.id, { applicable: !event.target.checked },
        ]);
    }

    async addSupplier() {
        await this._save("add_supplier_matrix_supplier", []);
    }

    async removeSupplier(supplier, confirmed = false) {
        try {
            const result = await this.orm.call(
                "purchase.request",
                "remove_supplier_matrix_supplier",
                [[this.props.requestId], supplier.id, confirmed]
            );
            if (result.confirmation_required) {
                this.dialog.add(ConfirmationDialog, {
                    title: "Supprimer le fournisseur",
                    body: `Les notes et commentaires de ${result.supplier_name} seront supprimés. Continuer ?`,
                    confirm: () => this.removeSupplier(supplier, true),
                    confirmLabel: "Supprimer",
                    cancelLabel: "Annuler",
                });
                return;
            }
            this.state.data = result;
        } catch (error) {
            this.notification.add(error.data?.message || error.message, { type: "danger" });
            await this.load();
        }
    }

    async downloadMatrix() {
        await this.load();
        const reportAction = await this.orm.call(
            "purchase.request",
            "action_download_supplier_matrix",
            [[this.props.requestId]]
        );
        return this.action.doAction(reportAction);
    }

    async _save(method, args) {
        try {
            this.state.data = await this.orm.call(
                "purchase.request", method, [[this.props.requestId], ...args]
            );
        } catch (error) {
            this.notification.add(error.data?.message || error.message, { type: "danger" });
            await this.load();
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
